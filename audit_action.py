#!/usr/bin/env python3
"""FacturLint GitHub Action — Stateless Factur-X 1.09.2 & BR-FR-CTC compliance auditor."""

from __future__ import annotations

import glob
import json
import mimetypes
import os
from pathlib import Path
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import uuid


def encode_multipart_file(field_name: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----FacturLintGABoundary{uuid.uuid4().hex}"
    ct = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    clean_name = Path(filename).name.replace('"', '\\"')

    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f'Content-Disposition: form-data; name="{field_name}"; filename="{clean_name}"\r\n'.encode("utf-8")
    )
    body.extend(f"Content-Type: {ct}\r\n\r\n".encode("utf-8"))
    body.extend(content)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    header = f"multipart/form-data; boundary={boundary}"
    return bytes(body), header


def post_validate(
    base_url: str,
    file_path: Path,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/validate"
    body, ct = encode_multipart_file("file", file_path.name, file_path.read_bytes())
    headers = {
        "User-Agent": "FacturLint-GitHub-Action/0.2.0",
        "Content-Type": ct,
        "Accept": "application/json",
    }
    if api_key:
        headers["X-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason} sur {url}: {raw}") from exc


def post_repair(
    base_url: str,
    file_path: Path,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/repair"
    body, ct = encode_multipart_file("file", file_path.name, file_path.read_bytes())
    headers = {
        "User-Agent": "FacturLint-GitHub-Action/0.2.0",
        "Content-Type": ct,
        "Accept": "application/json",
    }
    if api_key:
        headers["X-API-Key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason} sur {url}: {raw}") from exc


def main() -> None:
    files_pattern = os.getenv("INPUT_FILES", "**/*.pdf")
    api_key = os.getenv("INPUT_API_KEY", "").strip() or None
    fail_on_warning = os.getenv("INPUT_FAIL_ON_WARNING", "false").lower() in {"true", "1", "yes"}
    auto_repair = os.getenv("INPUT_AUTO_REPAIR", "false").lower() in {"true", "1", "yes"}
    base_url = os.getenv("INPUT_BASE_URL", "https://facturlint.com").strip()

    # Collect matching files
    matched_paths: list[Path] = []
    for pattern in files_pattern.splitlines():
        pattern = pattern.strip()
        if not pattern:
            continue
        for entry in glob.glob(pattern, recursive=True):
            p = Path(entry)
            if not p.is_file():
                continue
            # Ignore hidden folders or common build dirs
            parts = p.parts
            if any(part.startswith(".") or part in {"node_modules", "venv", ".venv", "dist", "build"} for part in parts):
                continue
            matched_paths.append(p)

    # De-duplicate
    seen: set[Path] = set()
    files: list[Path] = []
    for p in matched_paths:
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            files.append(p)

    if not files:
        print(f"::warning::FacturLint: Aucun fichier ne correspond au motif '{files_pattern}'.")
        _write_step_summary(
            "### 🔍 FacturLint — Audit Factur-X\n\nAucun fichier trouvé correspondant au motif spécifié.",
            [],
        )
        _write_output("total_scanned", "0")
        _write_output("total_compliant", "0")
        _write_output("total_issues", "0")
        sys.exit(0)

    print(f"FacturLint: Début de l'audit de {len(files)} fichier(s) via {base_url}...")

    total_scanned = len(files)
    total_compliant = 0
    total_issues = 0
    has_fatal_or_error = False
    has_warning = False
    results_table: list[dict[str, Any]] = []

    for file_p in files:
        rel_path = file_p.as_posix()
        try:
            report = post_validate(base_url, file_p, api_key=api_key)
        except Exception as exc:
            print(f"::error file={rel_path}::Erreur d'appel API FacturLint : {exc}")
            has_fatal_or_error = True
            results_table.append(
                {
                    "file": rel_path,
                    "status": "ERROR_API",
                    "valid": False,
                    "profile": "-",
                    "total": "-",
                    "issues_count": 1,
                    "repaired": False,
                }
            )
            continue

        valid = bool(report.get("valid"))
        status = report.get("status", "UNKNOWN")
        container = report.get("container", {})
        inv = report.get("invoice_summary", {})
        issues = report.get("issues", [])
        total_issues += len(issues)

        repaired = False
        if (
            not valid
            and auto_repair
            and status == "REPAIRABLE_ENVELOPE"
            and file_p.suffix.lower() == ".pdf"
        ):
            try:
                rep_res = post_repair(base_url, file_p, api_key=api_key)
                if rep_res.get("repaired") and rep_res.get("repaired_pdf_base64"):
                    import base64

                    file_p.write_bytes(base64.b64decode(rep_res["repaired_pdf_base64"]))
                    repaired = True
                    valid = True
                    status = "COMPLIANT (AUTO-RÉPARÉ)"
                    print(
                        f"::notice file={rel_path}::Enveloppe PDF/A-3b auto-réparée avec succès par FacturLint."
                    )
            except Exception as rep_err:
                print(f"::warning file={rel_path}::Échec de l'auto-réparation : {rep_err}")

        if valid:
            total_compliant += 1
            print(f"✅ {rel_path} : Conforme Factur-X 1.09.2 ({container.get('detected_profile', 'N/A')})")
        else:
            print(f"❌ {rel_path} : Non conforme ({status})")

        # Emit GitHub annotations
        for issue in issues:
            code = issue.get("code", "ANOMALY")
            sev = issue.get("severity", "error")
            msg = issue.get("message", "")
            raw_url = issue.get("doc_url") or f"/erreurs/{code}"
            doc_url = f"{base_url.rstrip('/')}{raw_url}" if raw_url.startswith("/") else raw_url
            anno_text = f"{msg} — Guide résolution : {doc_url}"

            if sev in {"fatal", "error"}:
                has_fatal_or_error = True
                print(f"::error file={rel_path},title={code}::{anno_text}")
            elif sev == "warning":
                has_warning = True
                print(f"::warning file={rel_path},title={code}::{anno_text}")
            else:
                print(f"::notice file={rel_path},title={code}::{anno_text}")

        total_ttc = (
            f"{inv.get('grand_total')} {inv.get('currency', 'EUR')}"
            if inv.get("grand_total")
            else "-"
        )
        results_table.append(
            {
                "file": rel_path,
                "status": status,
                "valid": valid,
                "profile": container.get("detected_profile") or "-",
                "total": total_ttc,
                "issues_count": len(issues),
                "repaired": repaired,
            }
        )

    # Write GitHub outputs
    _write_output("total_scanned", str(total_scanned))
    _write_output("total_compliant", str(total_compliant))
    _write_output("total_issues", str(total_issues))

    # Generate GitHub Step Summary Markdown
    _build_and_write_summary(
        results_table=results_table,
        total_scanned=total_scanned,
        total_compliant=total_compliant,
        total_issues=total_issues,
    )

    if has_fatal_or_error or (fail_on_warning and has_warning):
        print(
            "\n::error::FacturLint: Des anomalies non conformes à la norme Factur-X 1.09.2 ont été détectées."
        )
        sys.exit(1)

    print("\nFacturLint: Audit terminé avec succès ! Toutes les factures sont conformes.")
    sys.exit(0)


def _write_output(key: str, value: str) -> None:
    output_file = os.getenv("GITHUB_OUTPUT")
    if output_file and os.path.exists(output_file):
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def _write_step_summary(content: str, _: list[Any]) -> None:
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write(content + "\n")
        except Exception:
            pass


def _build_and_write_summary(
    results_table: list[dict[str, Any]],
    total_scanned: int,
    total_compliant: int,
    total_issues: int,
) -> None:
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    icon = "✅" if total_compliant == total_scanned else "⚠️"
    lines: list[str] = [
        f"## {icon} Rapport d'Audit FacturLint — Factur-X 1.09.2 & BR-FR-CTC",
        "",
        f"- **Factures auditées** : {total_scanned}",
        f"- **Factures conformes** : {total_compliant} / {total_scanned}",
        f"- **Anomalies totales** : {total_issues}",
        f"- **Moteur d'analyse** : Stateless déterministe ([FacturLint.com](https://facturlint.com))",
        "",
        "| Fichier | Statut | Profil | Total TTC | Anomalies | Auto-Réparé |",
        "| :--- | :--- | :--- | :--- | :---: | :---: |",
    ]

    for item in results_table:
        status_badge = "✅ CONFORME" if item["valid"] else f"❌ {item['status']}"
        repaired_badge = "Oui" if item["repaired"] else "-"
        lines.append(
            f"| `{item['file']}` | {status_badge} | {item['profile']} | {item['total']} | {item['issues_count']} | {repaired_badge} |"
        )

    lines.extend(
        [
            "",
            "> 💡 **Besoin de corriger une anomalie ?**",
            "> Consultez le catalogue officiel des 110+ erreurs normatives : [https://facturlint.com/erreurs](https://facturlint.com/erreurs)",
            "> ",
            "> Pour débloquer l'auto-réparation PDF/A-3b en illimité et l'audit par lot : [https://facturlint.com/#tarifs](https://facturlint.com/#tarifs)",
        ]
    )

    try:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()

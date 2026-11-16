# FacturLint — Factur-X 1.09.2 & BR-FR-CTC GitHub Action

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-FacturLint%20Audit-blue.svg?logo=github)](https://github.com/marketplace/actions/facturlint-factur-x-audit)
[![Stateless](https://img.shields.io/badge/privacy-100%25%20stateless-green.svg)](https://facturlint.com)
[![Factur-X](https://img.shields.io/badge/norm-Factur--X%201.09.2-orange.svg)](https://facturlint.com/docs)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

GitHub Action officielle pour auditer et valider automatiquement la conformité de vos factures électroniques **Factur-X 1.09.2**, **EN 16931** et **BR-FR-CTC** (Réforme française 2026, Chorus Pro et Plateformes Agréées / PDP).

Zéro stockage : vos factures sont analysées en mémoire vive de manière 100 % déterministe par le moteur [FacturLint.com](https://facturlint.com).

- 🌐 Site officiel : [https://facturlint.com](https://facturlint.com)
- 🔍 Catalogue des 110+ erreurs normatives : [https://facturlint.com/erreurs](https://facturlint.com/erreurs)
- 📚 Documentation API : [https://facturlint.com/docs](https://facturlint.com/docs)
- 💳 Tarifs & Clés API : [https://facturlint.com/#tarifs](https://facturlint.com/#tarifs)

---

## 🚀 Exemple Rapide (Copy-Paste)

Ajoutez ce workflow dans votre dépôt `.github/workflows/facturx-audit.yml` :

```yaml
name: "Audit Conformité Factur-X"

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  audit-invoices:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout du code
        uses: actions/checkout@v4

      - name: Valider les factures Factur-X
        uses: facturlint/facturx-action@v1
        with:
          files: "invoices/**/*.pdf"
          fail_on_warning: false
```

---

## 🛠️ Avec Auto-Réparation Automatique

Si vous générez des factures PDF dont l'enveloppe technique PDF/A-3b ou les métadonnées XMP sont imparfaites, activez l'auto-réparation en fournissant votre clé API FacturLint :

```yaml
      - name: Valider et Réparer l'enveloppe PDF/A-3b
        uses: facturlint/facturx-action@v1
        with:
          files: "dist/factures/*.pdf"
          api_key: ${{ secrets.FACTURLINT_API_KEY }}
          auto_repair: true
```

---

## 📋 Paramètres d'Entrée (`inputs`)

| Paramètre | Obligatoire | Valeur par défaut | Description |
| :--- | :---: | :---: | :--- |
| `files` | Non | `**/*.pdf` | Motif Glob ou chemin des factures à auditer (ex: `factures/**/*.pdf` ou `facture.pdf`). |
| `api_key` | Non | `""` | Clé API FacturLint. Facultative pour la validation simple (gratuite & stateless), requise pour l'auto-réparation. |
| `fail_on_warning` | Non | `false` | Si `true`, le job échoue dès qu'un avertissement (`warning`) est détecté. |
| `auto_repair` | Non | `false` | Si `true`, répare automatiquement l'enveloppe PDF/A-3b sans toucher aux montants. |
| `base_url` | Non | `https://facturlint.com` | URL de l'instance d'API FacturLint. |

---

## 📤 Données de Sortie (`outputs`)

| Sortie | Description |
| :--- | :--- |
| `total_scanned` | Nombre total de fichiers de factures scannés. |
| `total_compliant` | Nombre de factures 100 % conformes. |
| `total_issues` | Nombre total d'anomalies détectées (fatales, erreurs, avertissements). |

---

## 🔍 Annotations GitHub Automatiques

En cas de non-conformité, l'action produit des annotations visuelles directes dans l'interface GitHub (Pull Request / Commits) avec le lien vers la fiche de résolution officielle :

```
::error file=invoices/inv_001.pdf,title=BR-CO-15::Invoice total amount with VAT (BT-112) must equal sum of invoice total amount without VAT (BT-109) and invoice total VAT amount (BT-110). — Guide résolution : https://facturlint.com/erreurs/BR-CO-15
```

Un récapitulatif Markdown complet est automatiquement publié dans le **Job Summary** GitHub de chaque exécution.

---

## 📄 Licence & Contact

Distribué sous licence **MIT**.
Développé par **FacturLint** — [https://facturlint.com](https://facturlint.com).
Support & Contact : `contact@facturlint.com`.
Pour toute question normative, référez-vous au [catalogue officiel des erreurs](https://facturlint.com/erreurs).

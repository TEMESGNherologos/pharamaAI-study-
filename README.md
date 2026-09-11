# 🧬 Pharmacy Intelligence Platform — Stage 1 Portfolio Blueprint

> **Author**: 3rd-Year Pharmacy Student | Computational Pharmacogenomics  
> **Stack**: Python · SQL · R · PostgreSQL/SQLite · PharmGKB · OpenFDA  
> **Goal**: End-to-end system for adverse interaction flagging, weight-based dosing, and genomic variant risk stratification.

---

## 📁 Project Structure

```
project/
├── PHAI-101_Python/          # Python for Pharmacy Data Science
│   ├── drug_dosage_calculator.py
│   ├── pandas_cleaning_pipeline.py
│   └── notebooks/
│       └── PHAI101_intro.ipynb
├── PHAI-102_SQL/             # SQL for Clinical Databases
│   ├── schema.sql
│   ├── drug_interaction_queries.sql
│   └── ingest_openfda.py
├── PHAI-103_Biostatistics/   # Biostatistics & Statistical Genetics
│   ├── hardy_weinberg.py
│   ├── concentration_regression.py
│   └── notebooks/
│       └── PHAI103_stats.ipynb
├── PHAI-104_Genomics/        # Pharmacology & Genomics Bridge
│   ├── gene_drug_mapper.py
│   └── reports/
│       └── CYP2D6_codeine_report.md
├── PHAI-105_Writing/         # Academic & Professional Writing
│   └── pharmacogenomics_paper_outline.md
├── capstone/                 # Pharmacy Intelligence Database
│   ├── interaction_engine.py
│   ├── dosing_engine.py
│   ├── genomics_risk_engine.py
│   ├── database/
│   │   └── schema.sql
│   └── notebooks/
│       └── capstone_demo.ipynb
├── data/                     # Raw & processed datasets
│   ├── raw/
│   └── processed/
├── logs/                     # Daily progress logs
│   └── progress_log.md
├── requirements.txt
└── README.md
```

---

## 🗺️ Course Roadmap

| Code | Title | Core Output | Dataset |
|------|-------|-------------|---------|
| PHAI-101 | Python for Pharmacy Data Science | Dosage Calculator + Pandas Pipeline | PharmGKB CSVs |
| PHAI-102 | SQL for Clinical Databases | Relational Schema (500+ Drugs) + DDI Queries | OpenFDA + SQLite |
| PHAI-103 | Biostatistics & Statistical Genetics | HWE Analysis + Concentration Regression | Population Genetics |
| PHAI-104 | Pharmacology & Genomics Bridge | 6 Gene-Drug Mapping Reports (CYP450) | PharmGKB Annotations |
| PHAI-105 | Academic & Professional Writing | 5-Page PGx Paper on CYP2D6/Codeine | Zotero + APA |
| **Capstone** | **Pharmacy Intelligence Database** | **End-to-end PGx Interaction Platform** | **OpenFDA + PharmGKB** |

---

## ⏱️ Daily Study Schedule

| Time | Block | Focus |
|------|-------|-------|
| 2:00–2:30 PM | 🃏 Warm-up & Anki | Code snippets, SQL syntax, CYP2D6 phenotypes |
| 2:30–3:30 PM | 📚 Core Theory | Python/SQL modules or Biostatistics (HWE, ANOVA) |
| 3:30–4:30 PM | 💻 Hands-on Practice | Apply code to PharmGKB CSVs or OpenFDA JSON |
| 4:30–5:30 PM | 🧬 Domain Integration | Map drugs to variants (Codeine, Warfarin, Clopidogrel) |
| 5:30–6:00 PM | 🔀 Version Control | Git commit, docs update, progress log |

---

## 🚀 Quick Start

```bash
# 1. Clone and enter project
cd project

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize the SQLite database
python capstone/interaction_engine.py --init-db

# 5. Launch Jupyter demo
jupyter notebook capstone/notebooks/capstone_demo.ipynb
```

---

## 🔑 Key Target Drugs & Genes

| Drug | Gene | Variant | Clinical Impact |
|------|------|---------|-----------------|
| Codeine | CYP2D6 | *1/*2, PM/UM | Opioid toxicity / therapeutic failure |
| Warfarin | CYP2C9, VKORC1 | *2, *3, -1639G>A | Bleeding risk, dose variance |
| Clopidogrel | CYP2C19 | *2, *17 | Antiplatelet response |
| Tamoxifen | CYP2D6 | PM phenotype | Endoxifen levels, efficacy |
| Simvastatin | SLCO1B1 | rs4149056 | Myopathy risk |

---

## 📊 Capstone Architecture

```
OpenFDA API ──────┐
                  ├──► Python Ingestion Layer
PharmGKB API ─────┘         │
                             ▼
                    SQLite / PostgreSQL DB
                    ┌────────────────────┐
                    │ drugs              │
                    │ interactions       │
                    │ dosages            │
                    │ genomic_variants   │
                    │ patients           │
                    └────────────────────┘
                             │
                    ┌────────▼──────────┐
                    │ Interaction Engine │
                    │ Dosing Engine      │
                    │ Genomic Risk Engine│
                    └────────────────────┘
                             │
                    Jupyter Notebook Demo
```

---

*Last updated: 2026-09-11 | Stage 1 — Active Development*

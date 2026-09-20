#  API Integration Guide: openFDA & ClinPGx (PharmGKB)

Welcome to the **Pharmacy Intelligence Platform** API integration guide. This document provides a complete technical reference for querying public pharmacogenomics, drug safety, and prescribing data using **openFDA** and **ClinPGx / PharmGKB** REST APIs.

---

## 📌 APIs & Base Endpoints Summary

| Service | Host Base URL | Auth Requirement | Rate Limits | Primary Use Case |
| --- | --- | --- | --- | --- |
| **openFDA** | `[https://api.fda.gov](https://api.fda.gov)` | Optional (Free API key recommended) | **No Key:** 40 req/min, 1,000 req/day<br>

<br>**With Key:** 240 req/min, 120,000 req/day | FAERS adverse events, product labeling, boxed warnings, DDI sections

 |
| **ClinPGx** *(formerly PharmGKB)* | `[https://api.clinpgx.org/v1](https://api.clinpgx.org/v1)` | None required | 2 req/sec (120 req/min) | Gene-drug variants, CPIC dosing guidelines, clinical annotations

 |

> **⚠️ API Migration Notice:** PharmGKB transitioned its API infrastructure from `api.pharmgkb.org` to `api.clinpgx.org`. All queries should use `api.clinpgx.org`.

---

## 1. openFDA REST API Reference

openFDA provides structured JSON endpoints indexed by Elasticsearch.

### Query Syntax Rules

* **Field Filtering:** `search=field_name:value`
* **Exact Phrase Search:** `search=field_name:"phrase with spaces"`
* **Logical Operators:** `+AND+` (both terms match), `+` (either term matches)
* **Pagination Parameters:** `limit` (max 1000), `skip` (max 25000)
* **Aggregation:** `count=field_name.exact`

---

### Core openFDA Endpoints

#### A. Drug Labeling & Interactions

* **Endpoint:** `GET /drug/label.json`
* **Key Fields Returned:** `boxed_warning`, `drug_interactions`, `dosage_and_administration`, `contraindications`, `warnings_and_cautions`

**Example Query: Get Boxed Warnings & Interactions for Codeine**

```bash
curl -X GET "https://api.fda.gov/drug/label.json?search=openfda.generic_name:\"codeine\"&limit=1"

```

#### B. FAERS Adverse Event Reports

* **Endpoint:** `GET /drug/event.json`
* **Key Fields Returned:** `patient.reaction`, `patient.drug`, `serious`, `seriousnessdeath`

**Example Query: Top Reported Adverse Reactions for Warfarin**

```bash
curl -X GET "https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:\"WARFARIN\"&count=patient.reaction.reactionmeddrapt.exact"

```

#### C. National Drug Code (NDC) Directory

* **Endpoint:** `GET /drug/ndc.json`
* **Key Fields Returned:** `brand_name`, `generic_name`, `dosage_form`, `active_ingredients`, `pharm_class`

**Example Query: Query Drugs in the 'Opioid Agonist' Pharmacological Class**

```bash
curl -X GET "https://api.fda.gov/drug/ndc.json?search=pharm_class:\"Opioid Agonist\"&limit=10"

```

---

## 2. ClinPGx / PharmGKB REST API Reference

ClinPGx provides biological annotations, CPIC level-of-evidence scores, and gene-drug-variant mappings.

### Response Format

All endpoints return standard JSON objects structured around `data` arrays and entity IDs.

---

### Core ClinPGx Endpoints

#### A. Gene Endpoint

* **Endpoint:** `GET /data/gene`
* **Parameters:** `symbol` (e.g., `CYP2D6`, `CYP2C19`, `SLCO1B1`)



**Example Query: Retrieve CYP2D6 Metadata**

```bash
curl -X GET "https://api.clinpgx.org/v1/data/gene?symbol=CYP2D6"

```

#### B. Chemical / Drug Endpoint

* **Endpoint:** `GET /data/chemical`
* **Parameters:** `name` (e.g., `warfarin`, `clopidogrel`, `tamoxifen`)



**Example Query: Get PharmGKB Chemical Record for Warfarin**

```bash
curl -X GET "https://api.clinpgx.org/v1/data/chemical?name=warfarin"

```

#### C. Genomic Variant Endpoint

* **Endpoint:** `GET /data/variant`
* **Parameters:** `symbol` (rsID, e.g., `rs4149056`)



**Example Query: Fetch Variant Details for rs4149056 (SLCO1B1)**

```bash
curl -X GET "https://api.clinpgx.org/v1/data/variant?symbol=rs4149056"

```

#### D. Clinical Annotations Endpoint

* **Endpoint:** `GET /data/clinicalAnnotation`
* **Parameters:** `gene` or `location`

**Example Query: Get Clinical Level-of-Evidence Annotations for CYP2C19**

```bash
curl -X GET "https://api.clinpgx.org/v1/data/clinicalAnnotation?gene=CYP2C19"

```

---

## 3. End-to-End Ingestion Script (`ingest_openfda.py`)

Below is a complete, production-ready Python ingestion pipeline that fetches data from openFDA and ClinPGx, transforms the raw payload, and inserts normalized records into a SQLite database.

```python
#!/usr/bin/env python3
"""
ingest_openfda.py
-----------------
Pipeline script to ingest drug safety warnings from openFDA and 
genomic annotations from ClinPGx/PharmGKB into a local relational database.
"""

import time
import sqlite3
import requests
from typing import Dict, Any, Optional

# Base Configuration
OPENFDA_BASE = "https://api.fda.gov/drug"
CLINPGX_BASE = "https://api.clinpgx.org/v1/data"
DB_PATH = "clinic_db.sqlite"

def init_db():
    """Initializes schema tables if they do not exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drugs (
        drug_id INTEGER PRIMARY KEY AUTOINCREMENT,
        drug_name TEXT UNIQUE NOT NULL,
        boxed_warning TEXT,
        clinpgx_id TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gene_targets (
        gene_id INTEGER PRIMARY KEY AUTOINCREMENT,
        drug_name TEXT,
        gene_symbol TEXT,
        ncbi_id TEXT,
        FOREIGN KEY (drug_name) REFERENCES drugs(drug_name)
    )
    """)
    
    conn.commit()
    conn.close()

def fetch_openfda_warning(drug_name: str) -> Optional[str]:
    """Fetch boxed warnings for a given drug generic name from openFDA."""
    url = f"{OPENFDA_BASE}/label.json"
    params = {
        "search": f'openfda.generic_name:"{drug_name}"',
        "limit": 1
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                warnings = results[0].get("boxed_warning", [])
                return " ".join(warnings) if warnings else "No boxed warning found."
    except Exception as e:
        print(f"[openFDA Error] Failed to fetch {drug_name}: {e}")
    return None

def fetch_clinpgx_gene(gene_symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch gene data and PharmGKB/ClinPGx ID for a gene symbol."""
    url = f"{CLINPGX_BASE}/gene"
    params = {"symbol": gene_symbol}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json().get("data", [])
            if data:
                return {
                    "clinpgx_id": data[0].get("id"),
                    "ncbi_id": data[0].get("ncbiGeneId")
                }
    except Exception as e:
        print(f"[ClinPGx Error] Failed to fetch {gene_symbol}: {e}")
    return None

def process_pipeline(drug_gene_map: Dict[str, str]):
    """Runs end-to-end extraction, transformation, and database load."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for drug, gene in drug_gene_map.items():
        print(f"[*] Processing {drug} -> {gene}...")
        
        # 1. Fetch from openFDA
        warning = fetch_openfda_warning(drug)
        time.sleep(0.3)  # Rate limiting compliance
        
        # 2. Fetch from ClinPGx
        gene_info = fetch_clinpgx_gene(gene)
        time.sleep(0.5)  # ClinPGx limit: max 2 req/sec
        
        clinpgx_id = gene_info.get("clinpgx_id") if gene_info else None
        ncbi_id = gene_info.get("ncbi_id") if gene_info else None

        # 3. Load into Database
        cursor.execute("""
            INSERT INTO drugs (drug_name, boxed_warning, clinpgx_id)
            VALUES (?, ?, ?)
            ON CONFLICT(drug_name) DO UPDATE SET
                boxed_warning=excluded.boxed_warning,
                clinpgx_id=excluded.clinpgx_id
        """, (drug, warning, clinpgx_id))

        cursor.execute("""
            INSERT INTO gene_targets (drug_name, gene_symbol, ncbi_id)
            VALUES (?, ?, ?)
        """, (drug, gene, ncbi_id))

        conn.commit()

    conn.close()
    print("[✔] Ingestion complete. Data saved to clinic_db.sqlite.")

if __name__ == "__main__":
    # Key target drugs & genes mapping
    TARGETS = {
        "codeine": "CYP2D6",
        "warfarin": "CYP2C9",
        "clopidogrel": "CYP2C19",
        "simvastatin": "SLCO1B1"
    }
    process_pipeline(TARGETS)

```

---

## 4. API Error Handling Reference

| HTTP Code | Root Cause | Handling Strategy |
| --- | --- | --- |
| `400 Bad Request` | Malformed query syntax (e.g., missing quotes around multi-word terms). | Sanitize parameters; escape spaces as `%20` or double quotes. |
| `404 Not Found` | No record matches the search criteria in openFDA/ClinPGx. | Catch exception gracefully; return fallback value (`"No data found"`). |
| `429 Too Many Requests` | Exceeded rate limits (openFDA >240 req/min; ClinPGx >2 req/sec). | Implement exponential backoff (`time.sleep()`) and request throttling. |
| `500 / 503 Server Error` | Upstream API timeout or temporary maintenance outage. | Retry request up to 3 times before logging failure. |
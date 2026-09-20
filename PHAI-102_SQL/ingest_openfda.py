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
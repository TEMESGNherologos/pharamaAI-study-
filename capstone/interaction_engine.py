"""
Capstone: Pharmacy Intelligence Database
=========================================
Core Interaction Engine — Drug-Drug + PGx Risk Checker

This is the central logic module that integrates:
  1. Drug-drug interaction (DDI) lookup from SQLite DB
  2. PGx-adjusted dosing via patient genotype
  3. Adverse event risk scoring
  4. Structured JSON output for downstream reporting / Jupyter demo

Usage:
  python interaction_engine.py --init-db          # initialise DB with schema + seed data
  python interaction_engine.py                    # run demo query
"""

from __future__ import annotations
import argparse
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator
from loguru import logger


# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────

DB_PATH   = Path(__file__).parent / "database" / "pharmacy_intelligence.db"
SCHEMA_PATH = Path(__file__).parent / "database" / "schema.sql"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────
# Database Connection
# ──────────────────────────────────────────────────────────────

@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Yields a SQLite connection with foreign key support enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialise DB schema + seed data from schema.sql."""
    core_schema = Path(__file__).parent.parent / "PHAI-102_SQL" / "schema.sql"
    capstone_schema = Path(__file__).parent / "database" / "schema.sql"
    
    with get_connection() as conn:
        if core_schema.exists():
            conn.executescript(core_schema.read_text(encoding="utf-8"))
        if capstone_schema.exists():
            conn.executescript(capstone_schema.read_text(encoding="utf-8"))
            
    logger.success(f"Database initialised -> {DB_PATH}")


# ──────────────────────────────────────────────────────────────
# DDI Lookup
# ──────────────────────────────────────────────────────────────

def get_interaction(drug_a: str, drug_b: str) -> Optional[dict]:
    """
    Query drug_interactions table for a given pair (order-independent).
    Returns interaction dict or None.
    """
    query = """
        SELECT
            da.generic_name AS drug_a,
            db.generic_name AS drug_b,
            di.severity,
            di.mechanism,
            di.management,
            di.evidence_source
        FROM drug_interactions di
        JOIN drugs da ON da.drug_id = di.drug_a_id
        JOIN drugs db ON db.drug_id = di.drug_b_id
        WHERE (
            (LOWER(da.generic_name) = LOWER(?) AND LOWER(db.generic_name) = LOWER(?))
            OR
            (LOWER(da.generic_name) = LOWER(?) AND LOWER(db.generic_name) = LOWER(?))
        )
        LIMIT 1
    """
    with get_connection() as conn:
        row = conn.execute(query, (drug_a, drug_b, drug_b, drug_a)).fetchone()
    return dict(row) if row else None


# ──────────────────────────────────────────────────────────────
# PGx Lookup
# ──────────────────────────────────────────────────────────────

def get_pgx_recommendation(drug: str, gene: str, phenotype: str) -> Optional[dict]:
    """Retrieve CPIC-aligned dose recommendation for drug × gene × phenotype."""
    query = """
        SELECT
            d.generic_name      AS drug,
            g.symbol            AS gene,
            pa.phenotype,
            pa.recommendation,
            pa.evidence_level,
            pa.dose_change_pct
        FROM pgx_annotations pa
        JOIN drugs d ON d.drug_id = pa.drug_id
        JOIN genes g ON g.gene_id = pa.gene_id
        WHERE LOWER(d.generic_name) = LOWER(?)
          AND UPPER(g.symbol)       = UPPER(?)
          AND UPPER(pa.phenotype)   = UPPER(?)
        LIMIT 1
    """
    with get_connection() as conn:
        row = conn.execute(query, (drug, gene, phenotype)).fetchone()
    return dict(row) if row else None


# ──────────────────────────────────────────────────────────────
# Risk Scoring
# ──────────────────────────────────────────────────────────────

SEVERITY_SCORE = {
    "Contraindicated": 4,
    "Major":           3,
    "Moderate":        2,
    "Minor":           1,
}

PHENOTYPE_RISK_SCORE = {
    # CYP2D6
    "PM": 3,   # accumulation risk
    "IM": 2,
    "NM": 0,
    "UM": 3,   # toxicity risk (opioids) or therapeutic failure
}

def compute_risk_score(interactions: list[dict], phenotype: Optional[str]) -> dict:
    """
    Aggregate risk score from interactions + PGx phenotype.
    Scale: 0 (minimal) → 10 (critical)
    """
    ddi_score = sum(SEVERITY_SCORE.get(i.get("severity", ""), 0) for i in interactions)
    pgx_score = PHENOTYPE_RISK_SCORE.get((phenotype or "").upper(), 0)
    total = min(ddi_score + pgx_score, 10)

    return {
        "ddi_score":   ddi_score,
        "pgx_score":   pgx_score,
        "total_score": total,
        "risk_tier":   "Critical" if total >= 7 else
                       "High"     if total >= 5 else
                       "Moderate" if total >= 3 else
                       "Low",
    }


# ──────────────────────────────────────────────────────────────
# Primary API Function (as specified in roadmap)
# ──────────────────────────────────────────────────────────────

def check_drug_interaction(
    drug_a: str,
    drug_b: str,
    patient_genotype: str,
    gene: str = "CYP2D6",
) -> dict:
    """
    Full interaction check pipeline:
      1. DDI lookup for drug_a × drug_b
      2. PGx lookup for drug_a + patient_genotype
      3. Risk score computation
      4. Structured JSON-ready result

    Args:
        drug_a:           Primary drug name
        drug_b:           Co-administered drug name
        patient_genotype: Metabolizer phenotype (e.g. 'PM', 'UM', 'NM')
        gene:             Relevant metabolising gene (default: CYP2D6)

    Returns:
        dict with DDI status, PGx recommendation, risk score, and alerts
    """
    # Step 1 — DDI
    ddi = get_interaction(drug_a, drug_b)

    # Step 2 — PGx
    pgx = get_pgx_recommendation(drug_a, gene, patient_genotype)

    # Step 3 — Risk
    risk = compute_risk_score(
        interactions=[ddi] if ddi else [],
        phenotype=patient_genotype,
    )

    # Step 4 — Assemble result
    alerts: list[str] = []
    if ddi and ddi["severity"] in ("Contraindicated", "Major"):
        alerts.append(f"[{ddi['severity'].upper()}] interaction: {drug_a} + {drug_b} - {ddi['mechanism']}")
    if patient_genotype.upper() == "PM":
        alerts.append(f"[WARNING] Patient is {gene} Poor Metabolizer - risk of drug accumulation")
    if patient_genotype.upper() == "UM":
        alerts.append(f"[WARNING] Patient is {gene} Ultrarapid Metabolizer - risk of rapid conversion / toxicity")

    return {
        "drug_a":         drug_a,
        "drug_b":         drug_b,
        "patient_gene":   gene,
        "patient_genotype": patient_genotype,
        "ddi": ddi or {"status": "No interaction found in database"},
        "pgx": pgx or {"status": f"No PGx annotation for {drug_a} / {gene} / {patient_genotype}"},
        "risk": risk,
        "alerts": alerts,
        "recommendation_summary": (
            pgx["recommendation"] if pgx
            else "Consult clinical pharmacist — no PGx data available."
        ),
    }


# ──────────────────────────────────────────────────────────────
# Batch Patient Checker
# ──────────────────────────────────────────────────────────────

def batch_check(patient_records: list[dict]) -> list[dict]:
    """
    Run check_drug_interaction for a list of patient records.
    Each record: {'drug_a', 'drug_b', 'patient_genotype', 'gene'}
    """
    return [
        check_drug_interaction(**rec) for rec in patient_records
    ]


# ──────────────────────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pharmacy Intelligence — Interaction Engine")
    parser.add_argument("--init-db", action="store_true", help="Initialise SQLite database")
    args = parser.parse_args()

    if args.init_db:
        init_db()
    else:
        # Demo — no live DB needed; shows the API contract
        print("=" * 60)
        print("  Pharmacy Intelligence — Interaction Engine Demo")
        print("  (No database required for this output)")
        print("=" * 60)

        demo_result = {
            "drug_a":           "Codeine",
            "drug_b":           "Fluoxetine",
            "patient_gene":     "CYP2D6",
            "patient_genotype": "PM",
            "ddi": {
                "severity":  "Major",
                "mechanism": "Fluoxetine inhibits CYP2D6, converting NM -> PM phenotype; "
                             "codeine accumulation without active metabolite",
                "management": "Avoid combination. Use non-opioid analgesic.",
            },
            "pgx": {
                "phenotype":      "PM",
                "recommendation": "Avoid codeine — cannot convert to active morphine metabolite. "
                                  "Risk of therapeutic failure.",
                "evidence_level": "A",
                "dose_change_pct": -100,
            },
            "risk": {
                "ddi_score":   3,
                "pgx_score":   3,
                "total_score": 6,
                "risk_tier":   "High",
            },
            "alerts": [
                "[CRITICAL] Major interaction: Codeine + Fluoxetine - CYP2D6 inhibition",
                "[WARNING] Patient is CYP2D6 Poor Metabolizer - risk of drug accumulation",
            ],
        }

        print(json.dumps(demo_result, indent=2))

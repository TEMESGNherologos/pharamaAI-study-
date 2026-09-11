"""
Automated Test Suite for Pharmacy Intelligence Platform (Stage 1)
==================================================================
Tests deliverables across:
  - PHAI-101 (Dosage Calculator & Pandas Pipeline)
  - PHAI-103 (Hardy-Weinberg Equilibrium & Regression)
  - PHAI-104 (Gene-Drug Mapping)
  - Capstone (Interaction Engine & Database queries)
"""

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

# Add directories to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "PHAI-101_Python"))
sys.path.insert(0, str(PROJECT_ROOT / "PHAI-103_Biostatistics"))
sys.path.insert(0, str(PROJECT_ROOT / "PHAI-104_Genomics"))
sys.path.insert(0, str(PROJECT_ROOT / "capstone"))

# PHAI-101 imports
from drug_dosage_calculator import (
    Patient, Drug, calculate_dose, cockcroft_gault, renal_adjustment_factor, pgx_factor
)
from pandas_cleaning_pipeline import (
    standardise_columns, handle_missing, validate_drug_names, deduplicate
)

# PHAI-103 imports
from hardy_weinberg import GenotypeData, hardy_weinberg_test, batch_hwe_analysis
from concentration_regression import generate_demo_dataset, anova_by_phenotype, linear_regression_dose_conc

# PHAI-104 imports
from gene_drug_mapper import DRUG_GENE_KB, DrugGenePair, find_pair, generate_gene_drug_report

# Capstone imports
from interaction_engine import get_connection, get_interaction, check_drug_interaction


# ──────────────────────────────────────────────────────────────
# PHAI-101 Tests
# ──────────────────────────────────────────────────────────────

def test_dosage_calculator_standard_weight():
    """Verify standard weight-based calculation for patient with normal renal function."""
    drug = Drug(name="Amoxicillin", standard_dose_mg_per_kg=25.0, max_dose_mg=1500.0)
    patient = Patient(name="Alice", age=25, weight_kg=60.0, height_cm=165.0, sex="F", serum_creatinine=0.8)
    
    result = calculate_dose(patient=patient, drug=drug)
    assert result["base_dose_mg"] == 1500.0
    assert result["final_dose_mg"] == 1500.0
    assert result["renal_adjustment_factor"] == 1.0
    assert result["dose_capped"] is False


def test_dosage_calculator_renal_adjustment():
    """Verify CrCl-based dose reduction in renal impairment."""
    drug = Drug(name="Amoxicillin", standard_dose_mg_per_kg=10.0, max_dose_mg=1000.0)
    # CrCl ~ 29.5 mL/min (< 30) triggers 0.50 adjustment (CKD 4)
    patient = Patient(name="Alice", age=70, weight_kg=50.0, height_cm=160.0, sex="F", serum_creatinine=1.4)
    result = calculate_dose(patient=patient, drug=drug)
    assert result["renal_adjustment_factor"] == 0.5
    assert result["final_dose_mg"] == round(500.0 * 0.5, 2)


def test_dosage_calculator_max_cap():
    """Verify maximum dose ceiling enforcement."""
    drug = Drug(name="Amoxicillin", standard_dose_mg_per_kg=50.0, max_dose_mg=1000.0)
    patient = Patient(name="Bob", age=12, weight_kg=30.0, height_cm=140.0, sex="M", serum_creatinine=0.8)
    
    result = calculate_dose(patient=patient, drug=drug)
    assert result["base_dose_mg"] == 1000.0  # capped at max
    assert result["final_dose_mg"] == 1000.0
    assert result["dose_capped"] is True


def test_dosage_calculator_pgx_cyp2d6():
    """Verify PGx dose adjustments for CYP2D6 metabolizers."""
    drug = Drug(name="Codeine", standard_dose_mg_per_kg=0.5, max_dose_mg=60.0, gene="CYP2D6")
    patient_um = Patient(name="Charlie", age=35, weight_kg=75.0, height_cm=175.0, sex="M", serum_creatinine=0.9, genotype="UM")
    res_um = calculate_dose(patient=patient_um, drug=drug)
    assert res_um["pgx_adjustment_factor"] == 1.5
    assert res_um["final_dose_mg"] == round(res_um["renal_adjusted_dose_mg"] * 1.5, 2)


def test_pandas_cleaning_pipeline_steps():
    """Verify data pipeline cleans missing values, formats columns, and deduplicates."""
    raw_df = pd.DataFrame([
        {"Patient ID": 1, "Drug Name": "  codeine  ", "Age": 45, "Genotype": "NM"},
        {"Patient ID": 2, "Drug Name": "Warfarin", "Age": None, "Genotype": "IM"},
        {"Patient ID": 1, "Drug Name": "codeine", "Age": 45, "Genotype": "NM"},  # duplicate
    ])
    df = standardise_columns(raw_df)
    assert "patient_id" in df.columns
    assert "drug_name" in df.columns

    df, missing_summary = handle_missing(df)
    assert df["age"].isna().sum() == 0

    df = validate_drug_names(df, drug_col="drug_name")
    assert "drug_validated" in df.columns

    df = deduplicate(df, subset=["patient_id", "drug_normalised"])
    assert len(df) == 2


# ──────────────────────────────────────────────────────────────
# PHAI-103 Tests
# ──────────────────────────────────────────────────────────────

def test_hardy_weinberg_equilibrium_math():
    """Test HWE observed vs expected frequencies and Chi-square."""
    data = GenotypeData(gene="CYP2D6", variant="*1", population="TestPop", n_AA=490, n_Aa=420, n_aa=90)
    assert data.N == 1000
    assert round(data.freq_A, 2) == 0.70
    assert round(data.freq_a, 2) == 0.30
    
    res = hardy_weinberg_test(data)
    assert "chi2_statistic" in res
    assert "p_value" in res
    assert bool(res["in_HWE"]) is True


def test_concentration_regression_anova():
    """Test PK dataset generation and ANOVA significance."""
    df = generate_demo_dataset()
    assert len(df) == 160
    anova_res = anova_by_phenotype(df)
    assert bool(anova_res["significant"]) is True
    assert anova_res["p_value"] < 0.001


# ──────────────────────────────────────────────────────────────
# PHAI-104 Tests
# ──────────────────────────────────────────────────────────────

def test_gene_drug_mapper_lookup():
    """Test querying drug-gene pairs from knowledge base."""
    pairs = find_pair("Codeine", "CYP2D6")
    assert len(pairs) > 0
    pair = pairs[0]
    assert pair.evidence_level == "A"
    assert "PM" in pair.recommendations
    assert "UM" in pair.recommendations


def test_gene_drug_mapper_report_generation():
    """Test exporting PGx Markdown clinical summary report."""
    pairs = find_pair("Warfarin", "CYP2C9")
    assert len(pairs) > 0
    report_md = generate_gene_drug_report(pairs[0])
    assert "# Gene-Drug Report: Warfarin" in report_md
    assert "CYP2C9" in report_md


# ──────────────────────────────────────────────────────────────
# Capstone Tests
# ──────────────────────────────────────────────────────────────

def test_database_connection_and_seeded_tables():
    """Verify SQLite database has seeded drugs, interactions, and PGx annotations."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM drugs;")
        drug_count = cursor.fetchone()[0]
        assert drug_count >= 10

        cursor.execute("SELECT COUNT(*) FROM drug_interactions;")
        ddi_count = cursor.fetchone()[0]
        assert ddi_count >= 4

        cursor.execute("SELECT COUNT(*) FROM pgx_annotations;")
        pgx_count = cursor.fetchone()[0]
        assert pgx_count >= 4


def test_interaction_engine_check():
    """Verify DDI + PGx composite evaluation logic."""
    result = check_drug_interaction(
        drug_a="Codeine",
        drug_b="Fluoxetine",
        patient_genotype="PM",
        gene="CYP2D6"
    )
    assert result["risk"]["risk_tier"] in ["High", "Critical", "Moderate"]
    assert len(result["alerts"]) > 0
    assert result["ddi"]["severity"] == "Major"

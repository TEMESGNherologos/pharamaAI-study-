"""
PHAI-101: Python for Pharmacy Data Science
==========================================
Pandas Data Cleaning Pipeline — PharmGKB Drug-Response CSVs

Pipeline stages:
  1. Load raw PharmGKB / OpenFDA CSVs
  2. Standardise column names (snake_case)
  3. Handle missing values with domain-aware strategies
  4. Validate drug names against a known formulary
  5. Deduplicate records
  6. Export cleaned dataset + summary report
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np
from loguru import logger


# ──────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────
# Step 1: Load
# ──────────────────────────────────────────────────────────────

def load_csv(filepath: str | Path, **read_kwargs) -> pd.DataFrame:
    """Load a CSV file with basic validation."""
    fp = Path(filepath)
    if not fp.exists():
        raise FileNotFoundError(f"CSV not found: {fp}")
    df = pd.read_csv(fp, **read_kwargs)
    logger.info(f"Loaded '{fp.name}' — {len(df):,} rows × {df.shape[1]} cols")
    return df


# ──────────────────────────────────────────────────────────────
# Step 2: Standardise Column Names
# ──────────────────────────────────────────────────────────────

def standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert all column names to lowercase snake_case."""
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[\s\-/]+", "_", regex=True)
        .str.replace(r"[^\w]", "", regex=True)
    )
    logger.debug(f"Columns after standardisation: {df.columns.tolist()}")
    return df


# ──────────────────────────────────────────────────────────────
# Step 3: Handle Missing Values
# ──────────────────────────────────────────────────────────────

MISSING_STRATEGIES = {
    "numeric":     "median",     # impute numerics with column median
    "categorical": "mode",       # impute categoricals with column mode
    "identifier":  "drop_row",   # drop rows where key identifiers are null
}

IDENTIFIER_COLS = ["drug_name", "gene_symbol", "variant_id", "patient_id"]

def handle_missing(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Apply domain-aware missing value strategies.
    Returns (cleaned_df, missing_summary).
    """
    summary: dict[str, dict] = {}

    # Drop rows with null identifiers
    for col in IDENTIFIER_COLS:
        if col in df.columns:
            before = len(df)
            df = df.dropna(subset=[col])
            dropped = before - len(df)
            if dropped:
                logger.warning(f"Dropped {dropped} rows with null '{col}'")
                summary[col] = {"action": "drop_row", "rows_dropped": dropped}

    # Impute numerics
    num_cols = df.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        if df[col].isna().any():
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            summary[col] = {"action": "median_imputation", "value": median_val}
            logger.debug(f"Imputed '{col}' with median={median_val:.4f}")

    # Impute categoricals
    cat_cols = df.select_dtypes(include=["str", "category"]).columns
    for col in cat_cols:
        if df[col].isna().any():
            mode_val = df[col].mode()
            if len(mode_val):
                df[col] = df[col].fillna(mode_val[0])
                summary[col] = {"action": "mode_imputation", "value": mode_val[0]}
                logger.debug(f"Imputed '{col}' with mode='{mode_val[0]}'")

    return df, summary


# ──────────────────────────────────────────────────────────────
# Step 4: Drug Name Validation
# ──────────────────────────────────────────────────────────────

# Expand this set from your PharmGKB / Lippincott reference
KNOWN_FORMULARY = {
    "codeine", "warfarin", "clopidogrel", "tamoxifen", "simvastatin",
    "metformin", "atorvastatin", "omeprazole", "losartan", "metoprolol",
    "amoxicillin", "ciprofloxacin", "sertraline", "fluoxetine", "risperidone",
}

def validate_drug_names(
    df: pd.DataFrame,
    drug_col: str = "drug_name",
    known: Optional[set] = None,
) -> pd.DataFrame:
    """
    Add a 'drug_validated' flag column.
    Unrecognised drugs are flagged for manual review, NOT dropped.
    """
    if drug_col not in df.columns:
        logger.warning(f"Column '{drug_col}' not found — skipping validation")
        return df

    ref = known or KNOWN_FORMULARY
    df["drug_normalised"] = df[drug_col].str.lower().str.strip()
    df["drug_validated"] = df["drug_normalised"].isin(ref)

    unrecognised = (~df["drug_validated"]).sum()
    if unrecognised:
        logger.warning(
            f"{unrecognised} unrecognised drug names flagged for review "
            f"(see 'drug_validated' == False)"
        )
    return df


# ──────────────────────────────────────────────────────────────
# Step 5: Deduplication
# ──────────────────────────────────────────────────────────────

def deduplicate(df: pd.DataFrame, subset: Optional[list[str]] = None) -> pd.DataFrame:
    """Remove duplicate rows, keeping the first occurrence."""
    before = len(df)
    df = df.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)
    dupes = before - len(df)
    logger.info(f"Removed {dupes} duplicate rows → {len(df):,} rows remain")
    return df


# ──────────────────────────────────────────────────────────────
# Step 6: Export + Summary Report
# ──────────────────────────────────────────────────────────────

def export(df: pd.DataFrame, output_name: str) -> Path:
    """Save cleaned DataFrame to processed/ directory."""
    out_path = PROCESSED_DIR / output_name
    df.to_csv(out_path, index=False)
    logger.success(f"Saved cleaned data → {out_path}")
    return out_path


def generate_summary_report(
    raw_df: pd.DataFrame,
    clean_df: pd.DataFrame,
    missing_summary: dict,
) -> pd.DataFrame:
    """Print a side-by-side summary of before/after cleaning."""
    report = pd.DataFrame({
        "Metric": [
            "Total rows",
            "Total columns",
            "Missing cells",
            "Duplicate rows",
            "Unvalidated drugs",
        ],
        "Before": [
            len(raw_df),
            raw_df.shape[1],
            raw_df.isna().sum().sum(),
            raw_df.duplicated().sum(),
            "N/A",
        ],
        "After": [
            len(clean_df),
            clean_df.shape[1],
            clean_df.isna().sum().sum(),
            clean_df.duplicated().sum(),
            (~clean_df.get("drug_validated", pd.Series(True))).sum(),
        ],
    })
    print("\n" + "=" * 50)
    print("  CLEANING PIPELINE SUMMARY")
    print("=" * 50)
    print(report.to_string(index=False))
    print()
    return report


# ──────────────────────────────────────────────────────────────
# Full Pipeline Runner
# ──────────────────────────────────────────────────────────────

def run_pipeline(input_csv: str | Path, output_name: str = "cleaned_pharmgkb.csv") -> pd.DataFrame:
    """Execute the full cleaning pipeline end-to-end."""
    # Load
    raw_df = load_csv(input_csv)
    df = raw_df.copy()

    # Transform
    df = standardise_columns(df)
    df, missing_summary = handle_missing(df)
    df = validate_drug_names(df)
    df = deduplicate(df)

    # Report + Export
    generate_summary_report(raw_df, df, missing_summary)
    export(df, output_name)

    return df


# ──────────────────────────────────────────────────────────────
# CLI Demo
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        # Demo with synthetic data when no file is provided
        logger.info("No CSV provided — running demo with synthetic data")
        demo_df = pd.DataFrame({
            "Drug Name": ["Warfarin", "CODEINE", "warfarin", None, "Unknown_Drug"],
            "Gene Symbol": ["CYP2C9", "CYP2D6", "CYP2C9", "CYP2D6", "CYP3A4"],
            "Variant ID": ["rs1799853", "rs1065852", "rs1799853", None, "rs123456"],
            "Effect Size": [2.3, None, 2.3, 1.1, 0.9],
            "P-Value": [0.001, 0.045, 0.001, None, 0.12],
        })
        tmp = PROCESSED_DIR.parent / "raw" / "_demo_input.csv"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        demo_df.to_csv(tmp, index=False)
        run_pipeline(tmp, "demo_cleaned.csv")
    else:
        run_pipeline(sys.argv[1])

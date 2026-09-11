"""
PHAI-101: Python for Pharmacy Data Science
==========================================
Drug Dosage Calculator — Weight-based & Renal-adjusted dosing engine.

Supports:
  - mg/kg dosing calculations
  - CrCl-based renal adjustment (Cockcroft-Gault)
  - Pediatric vs adult cutoffs
  - Output as structured dict for pipeline integration
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math


# ──────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────

@dataclass
class Patient:
    name: str
    age: int                       # years
    weight_kg: float               # kilograms
    height_cm: float               # centimetres
    sex: str                       # 'M' or 'F'
    serum_creatinine: float        # mg/dL
    genotype: Optional[str] = None # e.g. 'CYP2D6 *1/*2'

    @property
    def is_pediatric(self) -> bool:
        return self.age < 18

    @property
    def bmi(self) -> float:
        h_m = self.height_cm / 100
        return round(self.weight_kg / (h_m ** 2), 1)


@dataclass
class Drug:
    name: str
    standard_dose_mg_per_kg: float
    max_dose_mg: float
    renal_adjustment: bool = True
    narrow_therapeutic_index: bool = False
    gene: Optional[str] = None          # primary metabolising gene
    pgx_flag: Optional[str] = None      # e.g. "CYP2D6 UM: reduce dose by 50%"


# ──────────────────────────────────────────────────────────────
# Creatinine Clearance — Cockcroft-Gault
# ──────────────────────────────────────────────────────────────

def cockcroft_gault(patient: Patient) -> float:
    """
    Returns estimated CrCl in mL/min.
    Female correction factor: × 0.85
    """
    sex_factor = 0.85 if patient.sex.upper() == 'F' else 1.0
    crcl = (
        (140 - patient.age) * patient.weight_kg
        / (72 * patient.serum_creatinine)
    ) * sex_factor
    return round(max(crcl, 0), 2)


# ──────────────────────────────────────────────────────────────
# Renal Adjustment Factor
# ──────────────────────────────────────────────────────────────

def renal_adjustment_factor(crcl: float) -> tuple[float, str]:
    """
    Returns (factor, stage_label) based on CrCl (mL/min).
    """
    if crcl >= 60:
        return (1.0, "Normal / Mild impairment")
    elif crcl >= 30:
        return (0.75, "Moderate impairment (CKD 3)")
    elif crcl >= 15:
        return (0.50, "Severe impairment (CKD 4)")
    else:
        return (0.25, "Kidney failure (CKD 5 / ESRD)")


# ──────────────────────────────────────────────────────────────
# PGx Adjustment (stub — populated from DB in capstone)
# ──────────────────────────────────────────────────────────────

PGX_ADJUSTMENT_TABLE: dict[str, dict[str, float]] = {
    "CYP2D6": {
        "PM":  0.5,   # Poor Metabolizer — accumulation risk
        "IM":  0.75,  # Intermediate Metabolizer
        "NM":  1.0,   # Normal / Extensive Metabolizer
        "UM":  1.5,   # Ultrarapid Metabolizer — under-dosing risk
    },
    "CYP2C19": {
        "PM":  0.5,
        "IM":  0.75,
        "NM":  1.0,
        "RM":  1.25,  # Rapid Metabolizer
        "UM":  1.5,
    },
    "CYP2C9": {
        "*1/*1": 1.0,
        "*1/*2": 0.85,
        "*1/*3": 0.70,
        "*2/*2": 0.60,
        "*2/*3": 0.45,
        "*3/*3": 0.30,
    },
}

def pgx_factor(gene: Optional[str], genotype: Optional[str]) -> tuple[float, str]:
    """
    Returns (pgx_factor, note) based on gene and patient genotype.
    Defaults to 1.0 (no adjustment) if data is missing.
    """
    if not gene or not genotype:
        return (1.0, "No PGx data — standard dosing applied")

    gene_table = PGX_ADJUSTMENT_TABLE.get(gene.upper(), {})
    factor = gene_table.get(genotype.upper(), None)

    if factor is None:
        return (1.0, f"Genotype '{genotype}' not in PGx table for {gene}")

    note = f"{gene} {genotype} → dose factor {factor}"
    return (factor, note)


# ──────────────────────────────────────────────────────────────
# Core Dose Calculator
# ──────────────────────────────────────────────────────────────

def calculate_dose(patient: Patient, drug: Drug) -> dict:
    """
    Full pipeline: weight-based → renal adjustment → PGx adjustment.

    Returns a structured result dict suitable for logging / DB storage.
    """
    # 1. Base dose
    base_dose_mg = patient.weight_kg * drug.standard_dose_mg_per_kg

    # 2. Cap at maximum
    capped = base_dose_mg > drug.max_dose_mg
    base_dose_mg = min(base_dose_mg, drug.max_dose_mg)

    # 3. Renal adjustment
    crcl = cockcroft_gault(patient)
    r_factor, renal_stage = (1.0, "N/A") if not drug.renal_adjustment \
        else renal_adjustment_factor(crcl)

    renal_dose_mg = base_dose_mg * r_factor

    # 4. PGx adjustment
    pgx_f, pgx_note = pgx_factor(drug.gene, patient.genotype)
    final_dose_mg = renal_dose_mg * pgx_f

    # 5. Narrow therapeutic index warning
    nti_warning = (
        f"⚠️  {drug.name} is a NARROW THERAPEUTIC INDEX drug — "
        "confirm dose with clinical pharmacist."
        if drug.narrow_therapeutic_index else None
    )

    return {
        "patient": patient.name,
        "drug": drug.name,
        "age_years": patient.age,
        "weight_kg": patient.weight_kg,
        "is_pediatric": patient.is_pediatric,
        "bmi": patient.bmi,
        "crcl_mL_min": crcl,
        "renal_stage": renal_stage,
        "base_dose_mg": round(base_dose_mg, 2),
        "dose_capped": capped,
        "renal_adjusted_dose_mg": round(renal_dose_mg, 2),
        "pgx_note": pgx_note,
        "final_dose_mg": round(final_dose_mg, 2),
        "nti_warning": nti_warning,
        "pgx_adjustment_factor": pgx_f,
        "renal_adjustment_factor": r_factor,
    }


# ──────────────────────────────────────────────────────────────
# CLI Demo
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    # Example: Codeine for a CYP2D6 Ultrarapid Metabolizer patient
    patient = Patient(
        name="John Doe",
        age=35,
        weight_kg=75.0,
        height_cm=178.0,
        sex="M",
        serum_creatinine=1.1,
        genotype="UM",
    )

    codeine = Drug(
        name="Codeine",
        standard_dose_mg_per_kg=0.5,
        max_dose_mg=60,
        renal_adjustment=True,
        narrow_therapeutic_index=False,
        gene="CYP2D6",
        pgx_flag="CYP2D6 UM: high conversion to morphine — risk of respiratory depression",
    )

    result = calculate_dose(patient, codeine)
    print(json.dumps(result, indent=2))

    print("\n--- PGx Flag ---")
    print(codeine.pgx_flag)

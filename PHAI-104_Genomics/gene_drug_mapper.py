"""
PHAI-104: Pharmacology & Genomics Bridge
=========================================
Gene-Drug Mapper — CYP450 Focus

Maps target drugs to their primary metabolising genes, generates
structured reports on clinical variant impact, and links to
PharmGKB/CPIC guideline recommendations.

Coverage: CYP2D6, CYP2C9, CYP2C19, CYP3A4/5, VKORC1, SLCO1B1
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import json
from pathlib import Path
from loguru import logger


# ──────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────

@dataclass
class VariantImpact:
    allele: str               # e.g. "*2", "rs1799853"
    phenotype: str            # PM, IM, NM, UM, etc.
    frequency_european: Optional[float] = None
    frequency_african: Optional[float] = None
    frequency_asian: Optional[float] = None
    clinical_impact: str = ""


@dataclass
class DrugGenePair:
    drug: str
    gene: str
    role: str                 # 'substrate', 'inhibitor', 'inducer'
    cpic_guideline: str
    evidence_level: str       # A, B, C, D
    variants: list[VariantImpact] = field(default_factory=list)
    recommendations: dict[str, str] = field(default_factory=dict)  # phenotype → recommendation
    pharmgkb_url: str = ""
    cpic_url: str = ""


# ──────────────────────────────────────────────────────────────
# Knowledge Base — 6 Key Drug-Gene Pairs (CYP450 Focus)
# ──────────────────────────────────────────────────────────────

DRUG_GENE_KB: list[DrugGenePair] = [

    # 1. Codeine / CYP2D6
    DrugGenePair(
        drug="Codeine",
        gene="CYP2D6",
        role="substrate",
        cpic_guideline="CPIC® Guideline for Codeine and CYP2D6",
        evidence_level="A",
        variants=[
            VariantImpact("*3", "PM", 0.02, 0.00, 0.01, "Null allele — no enzyme activity"),
            VariantImpact("*4", "PM", 0.19, 0.04, 0.01, "Most common PM allele in Europeans"),
            VariantImpact("*5", "PM", 0.02, 0.05, 0.01, "Gene deletion — null activity"),
            VariantImpact("*10","IM", 0.02, 0.06, 0.38, "Reduced activity, common in Asians"),
            VariantImpact("*17","IM", 0.00, 0.20, 0.00, "Reduced activity, African-specific"),
            VariantImpact("xN", "UM", 0.02, 0.08, 0.01, "Gene duplication — ultrarapid conversion"),
        ],
        recommendations={
            "PM": "Use alternative analgesic (tramadol caution, non-opioid preferred). "
                  "Codeine cannot be converted to morphine — therapeutic failure risk.",
            "IM": "Use lowest effective dose with frequent monitoring.",
            "NM": "Standard dosing per label.",
            "UM": "AVOID — increased morphine formation → respiratory depression risk. "
                  "FDA Black Box Warning for breastfeeding mothers.",
        },
        pharmgkb_url="https://www.pharmgkb.org/chemical/PA449088",
        cpic_url="https://cpicpgx.org/guidelines/guideline-for-codeine-and-cyp2d6/",
    ),

    # 2. Warfarin / CYP2C9 + VKORC1
    DrugGenePair(
        drug="Warfarin",
        gene="CYP2C9",
        role="substrate",
        cpic_guideline="CPIC® Guideline for Warfarin, CYP2C9, VKORC1, CYP4F2",
        evidence_level="A",
        variants=[
            VariantImpact("*2", "IM", 0.10, 0.02, 0.03, "rs1799853 — reduced warfarin clearance"),
            VariantImpact("*3", "PM", 0.07, 0.01, 0.02, "rs1057910 — severely reduced clearance"),
        ],
        recommendations={
            "*1/*1": "Standard initial dose per clinical algorithm.",
            "*1/*2": "Reduce initial dose by 15–20%.",
            "*1/*3": "Reduce initial dose by 30–40%; more frequent INR monitoring.",
            "*2/*3": "Reduce initial dose by 50–60%; high bleeding risk.",
            "*3/*3": "Reduce dose by 70–80%; specialist guidance required.",
        },
        pharmgkb_url="https://www.pharmgkb.org/chemical/PA451906",
        cpic_url="https://cpicpgx.org/guidelines/guideline-for-warfarin-and-cyp2c9-vkorc1/",
    ),

    # 3. Clopidogrel / CYP2C19
    DrugGenePair(
        drug="Clopidogrel",
        gene="CYP2C19",
        role="substrate",
        cpic_guideline="CPIC® Guideline for Clopidogrel and CYP2C19",
        evidence_level="A",
        variants=[
            VariantImpact("*2", "PM/IM", 0.15, 0.17, 0.29, "Loss-of-function — reduced active metabolite"),
            VariantImpact("*3", "PM",    0.00, 0.00, 0.05, "Loss-of-function — common in East Asians"),
            VariantImpact("*17","UM",    0.21, 0.16, 0.03, "Increased activation — bleeding risk"),
        ],
        recommendations={
            "PM":  "AVOID clopidogrel — use prasugrel or ticagrelor (if eligible).",
            "IM":  "Consider alternative antiplatelet agent. Discuss with cardiologist.",
            "NM":  "Standard clopidogrel dosing per label.",
            "RM":  "Standard dosing; slightly higher antiplatelet effect.",
            "UM":  "Increased bleeding risk; consider dose reduction or alternative.",
        },
        pharmgkb_url="https://www.pharmgkb.org/chemical/PA449053",
        cpic_url="https://cpicpgx.org/guidelines/guideline-for-clopidogrel-and-cyp2c19/",
    ),

    # 4. Tamoxifen / CYP2D6
    DrugGenePair(
        drug="Tamoxifen",
        gene="CYP2D6",
        role="substrate",
        cpic_guideline="CPIC® Guideline for Tamoxifen and CYP2D6",
        evidence_level="A",
        variants=[
            VariantImpact("*4", "PM", 0.19, 0.04, 0.01, "Low endoxifen — reduced efficacy"),
            VariantImpact("*10","IM", 0.02, 0.06, 0.38, "Reduced endoxifen — lower efficacy"),
        ],
        recommendations={
            "PM":  "Consider aromatase inhibitor (anastrozole) for post-menopausal patients.",
            "IM":  "Avoid CYP2D6 inhibitors (paroxetine, fluoxetine). Higher tamoxifen dose (40mg) may be considered.",
            "NM":  "Standard tamoxifen 20 mg/day.",
            "UM":  "Standard dosing — possible increased endoxifen levels.",
        },
        pharmgkb_url="https://www.pharmgkb.org/chemical/PA451581",
        cpic_url="https://cpicpgx.org/guidelines/cpic-guideline-for-tamoxifen-based-on-cyp2d6-genotype/",
    ),

    # 5. Simvastatin / SLCO1B1
    DrugGenePair(
        drug="Simvastatin",
        gene="SLCO1B1",
        role="substrate",
        cpic_guideline="CPIC® Guideline for Simvastatin and SLCO1B1",
        evidence_level="A",
        variants=[
            VariantImpact("rs4149056 (T>C)", "Decreased function",
                          0.19, 0.02, 0.16,
                          "Increased statin plasma levels → myopathy risk"),
        ],
        recommendations={
            "Normal function":    "Standard simvastatin dosing up to 40 mg/day.",
            "Decreased function": "Avoid simvastatin >20 mg/day. Consider rosuvastatin/pravastatin.",
            "Poor function":      "Avoid simvastatin. Use rosuvastatin (SLCO1B1-independent).",
        },
        pharmgkb_url="https://www.pharmgkb.org/chemical/PA451363",
        cpic_url="https://cpicpgx.org/guidelines/cpic-guideline-for-simvastatin-and-slco1b1/",
    ),

    # 6. Fluorouracil / DPYD
    DrugGenePair(
        drug="Fluorouracil (5-FU)",
        gene="DPYD",
        role="substrate",
        cpic_guideline="CPIC® Guideline for Fluoropyrimidines and DPYD",
        evidence_level="A",
        variants=[
            VariantImpact("*2A (rs3918290)",     "PM", 0.01, 0.00, 0.00, "Splice site — no DPYD activity"),
            VariantImpact("c.2846A>T (rs67376798)","IM",0.01, 0.01, 0.00, "Significantly reduced activity"),
            VariantImpact("HapB3 (rs75017182)",  "IM", 0.02, 0.01, 0.00, "Reduced activity"),
        ],
        recommendations={
            "PM":  "AVOID fluoropyrimidines. If unavoidable, reduce dose by ≥50% and monitor closely.",
            "IM":  "Start at 50% dose reduction. Titrate upward based on tolerability.",
            "NM":  "Standard dosing per treatment protocol.",
        },
        pharmgkb_url="https://www.pharmgkb.org/chemical/PA128406956",
        cpic_url="https://cpicpgx.org/guidelines/guideline-for-fluoropyrimidines-and-dpyd/",
    ),
]


# ──────────────────────────────────────────────────────────────
# Report Generator
# ──────────────────────────────────────────────────────────────

def generate_gene_drug_report(pair: DrugGenePair) -> str:
    """Generate a Markdown-formatted gene-drug mapping report."""
    lines = [
        f"# Gene-Drug Report: {pair.drug} × {pair.gene}",
        f"",
        f"**Role**: {pair.role.capitalize()}  ",
        f"**CPIC Guideline**: {pair.cpic_guideline}  ",
        f"**Evidence Level**: {pair.evidence_level}  ",
        f"**PharmGKB**: {pair.pharmgkb_url}  ",
        f"**CPIC URL**: {pair.cpic_url}",
        f"",
        f"---",
        f"",
        f"## Key Variants",
        f"",
        f"| Allele | Phenotype | EUR% | AFR% | ASN% | Clinical Impact |",
        f"|--------|-----------|------|------|------|-----------------|",
    ]
    for v in pair.variants:
        lines.append(
            f"| {v.allele} | {v.phenotype} "
            f"| {(v.frequency_european or 0)*100:.1f}% "
            f"| {(v.frequency_african or 0)*100:.1f}% "
            f"| {(v.frequency_asian or 0)*100:.1f}% "
            f"| {v.clinical_impact} |"
        )

    lines += [
        f"",
        f"## Clinical Recommendations by Phenotype",
        f"",
    ]
    for phenotype, rec in pair.recommendations.items():
        lines.append(f"### {phenotype}")
        lines.append(f"{rec}")
        lines.append("")

    return "\n".join(lines)


def generate_all_reports(output_dir: str = "PHAI-104_Genomics/reports") -> None:
    """Generate and save Markdown reports for all pairs in the KB."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for pair in DRUG_GENE_KB:
        report = generate_gene_drug_report(pair)
        filename = f"{pair.drug.replace(' ', '_').replace('/', '-')}_{pair.gene}.md"
        fp = out / filename
        fp.write_text(report, encoding="utf-8")
        logger.success(f"Report saved → {fp}")


def find_pair(drug: str, gene: Optional[str] = None) -> list[DrugGenePair]:
    """Look up gene-drug pairs by drug name (and optionally gene)."""
    results = [
        p for p in DRUG_GENE_KB
        if p.drug.lower() == drug.lower()
        and (gene is None or p.gene.upper() == gene.upper())
    ]
    return results


# ──────────────────────────────────────────────────────────────
# CLI Demo
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  PHAI-104: Gene-Drug Mapper — CYP450 Focus")
    print("=" * 60)

    # Quick lookup demo
    pair = find_pair("Clopidogrel", "CYP2C19")
    if pair:
        print(generate_gene_drug_report(pair[0]))

    print("\n[Generating all 6 reports...]")
    generate_all_reports()
    print("Done.")

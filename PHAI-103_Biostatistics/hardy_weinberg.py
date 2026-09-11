"""
PHAI-103: Biostatistics & Statistical Genetics
===============================================
Hardy-Weinberg Equilibrium (HWE) Analysis — CYP2D6

Workflow:
  1. Load allele frequency data (PharmGKB / gnomAD format)
  2. Compute observed vs expected genotype frequencies
  3. Chi-squared HWE test
  4. Stratified analysis by metabolizer phenotype
  5. Export results + publication-ready plot
"""

from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from loguru import logger


# ──────────────────────────────────────────────────────────────
# Data Model
# ──────────────────────────────────────────────────────────────

@dataclass
class GenotypeData:
    """Observed genotype counts for a biallelic locus."""
    gene: str
    variant: str          # e.g. CYP2D6 *1/*2 diplotype grouping
    population: str
    n_AA: int             # homozygous reference
    n_Aa: int             # heterozygous
    n_aa: int             # homozygous alternate

    @property
    def N(self) -> int:
        return self.n_AA + self.n_Aa + self.n_aa

    @property
    def freq_A(self) -> float:
        """Major allele frequency (p)."""
        return (2 * self.n_AA + self.n_Aa) / (2 * self.N)

    @property
    def freq_a(self) -> float:
        """Minor allele frequency (q)."""
        return 1.0 - self.freq_A


# ──────────────────────────────────────────────────────────────
# HWE Calculator
# ──────────────────────────────────────────────────────────────

def hardy_weinberg_test(data: GenotypeData, alpha: float = 0.05) -> dict:
    """
    Perform Chi-squared test for Hardy-Weinberg Equilibrium.

    H₀: Population is in HWE (random mating, no selection)
    H₁: Significant deviation from HWE

    Returns full result dictionary.
    """
    p = data.freq_A
    q = data.freq_a
    N = data.N

    # Expected counts under HWE
    expected_AA = p**2 * N
    expected_Aa = 2 * p * q * N
    expected_aa = q**2 * N

    observed = np.array([data.n_AA, data.n_Aa, data.n_aa])
    expected = np.array([expected_AA, expected_Aa, expected_aa])

    # Chi-squared statistic (1 df: 3 classes − 1 estimated param − 1 = 1)
    chi2_stat, p_value = stats.chisquare(f_obs=observed, f_exp=expected, ddof=1)

    in_hwe = p_value >= alpha

    result = {
        "gene":           data.gene,
        "variant":        data.variant,
        "population":     data.population,
        "N":              N,
        "p_allele_freq":  round(p, 4),
        "q_allele_freq":  round(q, 4),
        "obs_AA":         data.n_AA,
        "obs_Aa":         data.n_Aa,
        "obs_aa":         data.n_aa,
        "exp_AA":         round(expected_AA, 2),
        "exp_Aa":         round(expected_Aa, 2),
        "exp_aa":         round(expected_aa, 2),
        "chi2_statistic": round(chi2_stat, 4),
        "p_value":        round(p_value, 6),
        "degrees_of_freedom": 1,
        "alpha":          alpha,
        "in_HWE":         in_hwe,
        "interpretation": (
            f"Population IS in HWE (χ²={chi2_stat:.3f}, p={p_value:.4f} ≥ {alpha})"
            if in_hwe else
            f"Population DEVIATES from HWE (χ²={chi2_stat:.3f}, p={p_value:.4f} < {alpha})"
        ),
    }

    logger.info(result["interpretation"])
    return result


# ──────────────────────────────────────────────────────────────
# Batch Analysis Across Populations
# ──────────────────────────────────────────────────────────────

def batch_hwe_analysis(records: list[GenotypeData], alpha: float = 0.05) -> pd.DataFrame:
    """Run HWE test on multiple populations and return summary DataFrame."""
    results = [hardy_weinberg_test(r, alpha=alpha) for r in records]
    return pd.DataFrame(results)


# ──────────────────────────────────────────────────────────────
# Visualization — Observed vs Expected Bar Chart
# ──────────────────────────────────────────────────────────────

def plot_hwe(result: dict, outpath: Optional[str] = None) -> None:
    """
    Grouped bar chart: Observed vs Expected genotype counts.
    """
    genotypes = ["AA (Ref/Ref)", "Aa (Ref/Alt)", "aa (Alt/Alt)"]
    observed = [result["obs_AA"], result["obs_Aa"], result["obs_aa"]]
    expected = [result["exp_AA"], result["exp_Aa"], result["exp_aa"]]

    x = np.arange(len(genotypes))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))
    sns.set_style("whitegrid")

    bars_obs = ax.bar(x - width/2, observed, width, label="Observed", color="#2E86AB", alpha=0.9)
    bars_exp = ax.bar(x + width/2, expected, width, label="Expected (HWE)", color="#A23B72", alpha=0.9)

    ax.set_xlabel("Genotype Class", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    ax.set_title(
        f"HWE Analysis — {result['gene']} ({result['variant']})\n"
        f"Population: {result['population']} | n={result['N']}\n"
        f"χ²={result['chi2_statistic']:.3f}  p={result['p_value']:.4f}  "
        f"{'✅ In HWE' if result['in_HWE'] else '⚠️ Deviation Detected'}",
        fontsize=11
    )
    ax.set_xticks(x)
    ax.set_xticklabels(genotypes)
    ax.legend()

    plt.tight_layout()
    if outpath:
        plt.savefig(outpath, dpi=150)
        logger.success(f"HWE plot saved → {outpath}")
    else:
        plt.show()


# ──────────────────────────────────────────────────────────────
# Demo — CYP2D6 Across Populations
# ──────────────────────────────────────────────────────────────

# Approximate CYP2D6 *1 (functional) allele frequencies
# Source: PharmGKB population annotations (illustrative values)
CYP2D6_DEMO_DATA = [
    GenotypeData("CYP2D6", "*1 allele", "European",       n_AA=740, n_Aa=220, n_aa=40),
    GenotypeData("CYP2D6", "*1 allele", "African",        n_AA=600, n_Aa=310, n_aa=90),
    GenotypeData("CYP2D6", "*1 allele", "East Asian",     n_AA=820, n_Aa=160, n_aa=20),
    GenotypeData("CYP2D6", "*1 allele", "South Asian",    n_AA=710, n_Aa=240, n_aa=50),
    GenotypeData("CYP2D6", "*1 allele", "Admixed American",n_AA=680,n_Aa=270, n_aa=50),
]


if __name__ == "__main__":
    print("=" * 60)
    print("  CYP2D6 Hardy-Weinberg Equilibrium Analysis")
    print("=" * 60)

    df_results = batch_hwe_analysis(CYP2D6_DEMO_DATA)

    # Display summary
    cols = ["population", "N", "p_allele_freq", "q_allele_freq",
            "chi2_statistic", "p_value", "in_HWE"]
    print(df_results[cols].to_string(index=False))

    # Plot one population
    first_result = hardy_weinberg_test(CYP2D6_DEMO_DATA[0])
    plot_hwe(first_result, outpath=None)   # change to a filepath to save

    # Export
    out = "data/processed/hwe_cyp2d6_results.csv"
    df_results.to_csv(out, index=False)
    print(f"\nResults saved → {out}")

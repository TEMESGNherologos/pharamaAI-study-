"""
PHAI-103: Biostatistics & Statistical Genetics
===============================================
Plasma Drug Concentration Regression Analysis

Models:
  1. Linear regression — dose vs. trough concentration
  2. One-way ANOVA — concentration across CYP2D6 metabolizer classes
  3. Post-hoc Tukey HSD — pairwise group comparisons
  4. Log-linear pharmacokinetic model
  5. Publication-ready visualisations
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.multicomp import pairwise_tukeyhsd
import matplotlib.pyplot as plt
import seaborn as sns
from loguru import logger


# ──────────────────────────────────────────────────────────────
# Synthetic Dataset (replace with real PharmGKB/clinical data)
# ──────────────────────────────────────────────────────────────

np.random.seed(42)

METABOLIZER_PHENOTYPES = ["PM", "IM", "NM", "UM"]

# Simulate trough concentrations (ng/mL) per phenotype class
# PMs accumulate drug → higher Cmin; UMs clear rapidly → lower Cmin
CONCENTRATION_MEANS = {"PM": 28.0, "IM": 18.0, "NM": 10.0, "UM": 5.0}
CONCENTRATION_STD   = {"PM": 6.0,  "IM": 4.5,  "NM": 3.0,  "UM": 2.0}
N_PER_GROUP = 40

def generate_demo_dataset() -> pd.DataFrame:
    records = []
    for phenotype in METABOLIZER_PHENOTYPES:
        mu  = CONCENTRATION_MEANS[phenotype]
        sig = CONCENTRATION_STD[phenotype]
        concentrations = np.random.normal(mu, sig, N_PER_GROUP).clip(min=0.1)
        doses = np.random.uniform(30, 60, N_PER_GROUP)  # Codeine mg
        for conc, dose in zip(concentrations, doses):
            records.append({
                "phenotype":      phenotype,
                "dose_mg":        round(dose, 1),
                "concentration":  round(conc, 2),   # morphine trough ng/mL
            })
    return pd.DataFrame(records)


# ──────────────────────────────────────────────────────────────
# 1. Linear Regression — Dose vs Concentration
# ──────────────────────────────────────────────────────────────

def linear_regression_dose_conc(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    """
    OLS: concentration ~ dose_mg
    Returns fitted model (statsmodels).
    """
    X = sm.add_constant(df["dose_mg"])
    y = df["concentration"]
    model = sm.OLS(y, X).fit()
    logger.info(f"Linear Regression R²={model.rsquared:.4f}  "
                f"p(dose)={model.pvalues['dose_mg']:.4f}")
    print(model.summary())
    return model


# ──────────────────────────────────────────────────────────────
# 2. One-Way ANOVA — Concentration by Metabolizer Class
# ──────────────────────────────────────────────────────────────

def anova_by_phenotype(df: pd.DataFrame) -> dict:
    """
    One-way ANOVA: H₀ — mean concentrations equal across PM/IM/NM/UM.
    Returns F-statistic, p-value, and eta-squared (effect size).
    """
    groups = [
        df.loc[df["phenotype"] == ph, "concentration"].values
        for ph in METABOLIZER_PHENOTYPES
    ]
    F, p = stats.f_oneway(*groups)

    # Eta-squared (η²) — proportion of variance explained by phenotype
    grand_mean = df["concentration"].mean()
    ss_between = sum(
        len(g) * (g.mean() - grand_mean)**2 for g in groups
    )
    ss_total = sum((df["concentration"] - grand_mean)**2)
    eta_sq = ss_between / ss_total

    result = {
        "F_statistic": round(F, 4),
        "p_value":     round(p, 8),
        "eta_squared": round(eta_sq, 4),
        "significant": p < 0.05,
        "interpretation": (
            f"F={F:.2f}, p={p:.6f} → "
            f"{'Significant difference' if p < 0.05 else 'No significant difference'} "
            f"across metabolizer phenotypes (η²={eta_sq:.3f})"
        ),
    }
    logger.info(result["interpretation"])
    return result


# ──────────────────────────────────────────────────────────────
# 3. Tukey HSD Post-Hoc
# ──────────────────────────────────────────────────────────────

def tukey_posthoc(df: pd.DataFrame) -> pd.DataFrame:
    """Pairwise Tukey HSD — identifies which phenotype pairs differ."""
    tukey = pairwise_tukeyhsd(
        endog=df["concentration"],
        groups=df["phenotype"],
        alpha=0.05,
    )
    print(tukey)
    result_df = pd.DataFrame(
        data=tukey._results_table.data[1:],
        columns=tukey._results_table.data[0],
    )
    return result_df


# ──────────────────────────────────────────────────────────────
# 4. Log-Linear Pharmacokinetic Model
# ──────────────────────────────────────────────────────────────

def log_linear_pk_model(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    """
    Log-linear: log(concentration) ~ dose_mg + phenotype
    Phenotype encoded as dummy variables.
    """
    df = df.copy()
    df["log_conc"] = np.log(df["concentration"])
    model = smf.ols("log_conc ~ dose_mg + C(phenotype, Treatment('NM'))", data=df).fit()
    logger.info(f"Log-linear PK model  R²={model.rsquared:.4f}")
    print(model.summary())
    return model


# ──────────────────────────────────────────────────────────────
# 5. Visualisations
# ──────────────────────────────────────────────────────────────

PHENOTYPE_COLORS = {
    "PM": "#E63946",   # Red — accumulation risk
    "IM": "#F4A261",   # Orange
    "NM": "#2A9D8F",   # Teal — normal
    "UM": "#457B9D",   # Blue — clearance risk
}

def plot_concentration_by_phenotype(df: pd.DataFrame, outpath: Optional[str] = None) -> None:
    """Box + strip plot of drug concentration by CYP2D6 phenotype."""
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.set_style("whitegrid")

    sns.boxplot(
        data=df, x="phenotype", y="concentration",
        order=METABOLIZER_PHENOTYPES,
        palette=PHENOTYPE_COLORS,
        width=0.5, linewidth=1.5, ax=ax,
        fliersize=0,
    )
    sns.stripplot(
        data=df, x="phenotype", y="concentration",
        order=METABOLIZER_PHENOTYPES,
        palette=PHENOTYPE_COLORS,
        size=4, alpha=0.5, jitter=True, ax=ax,
    )

    ax.set_xlabel("CYP2D6 Metabolizer Phenotype", fontsize=12)
    ax.set_ylabel("Trough Concentration (ng/mL)", fontsize=12)
    ax.set_title(
        "Codeine-derived Morphine Trough Concentrations by CYP2D6 Phenotype\n"
        "PM = Poor, IM = Intermediate, NM = Normal, UM = Ultrarapid",
        fontsize=11
    )

    plt.tight_layout()
    if outpath:
        plt.savefig(outpath, dpi=150)
        logger.success(f"Plot saved → {outpath}")
    else:
        plt.show()


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Plasma Concentration Regression — CYP2D6 / Codeine")
    print("=" * 60)

    df = generate_demo_dataset()
    print(f"\nDataset: {len(df)} observations | {df['phenotype'].value_counts().to_dict()}\n")

    # ANOVA
    print("\n[1] One-Way ANOVA")
    anova_res = anova_by_phenotype(df)
    print(anova_res["interpretation"])

    # Post-hoc
    print("\n[2] Tukey HSD Post-Hoc Comparisons")
    tukey_df = tukey_posthoc(df)

    # Linear regression (overall)
    print("\n[3] Linear Regression: Dose → Concentration")
    lm = linear_regression_dose_conc(df)

    # Log-linear PK model
    print("\n[4] Log-Linear PK Model")
    pk_model = log_linear_pk_model(df)

    # Plot
    print("\n[5] Generating visualisation...")
    plot_concentration_by_phenotype(df)

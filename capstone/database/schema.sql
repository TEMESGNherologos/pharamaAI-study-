-- ============================================================
-- Capstone: Pharmacy Intelligence Database
-- Extended Schema — Extends PHAI-102 schema with capstone tables
-- ============================================================

-- NOTE: Run PHAI-102_SQL/schema.sql first, then this file.

PRAGMA foreign_keys = ON;

-- ──────────────────────────────────────────────────────────────
-- PATIENT MEDICATIONS (junction — n:m patients ↔ drugs)
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS patient_medications (
    pm_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER NOT NULL REFERENCES patients(patient_id),
    drug_id      INTEGER NOT NULL REFERENCES drugs(drug_id),
    dose_mg      REAL,
    frequency    TEXT,
    start_date   TEXT,
    end_date     TEXT,
    indication   TEXT
);

CREATE INDEX IF NOT EXISTS idx_pm_patient ON patient_medications(patient_id);
CREATE INDEX IF NOT EXISTS idx_pm_drug    ON patient_medications(drug_id);

-- ──────────────────────────────────────────────────────────────
-- ADVERSE EVENTS LOG
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS adverse_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER NOT NULL REFERENCES patients(patient_id),
    drug_id      INTEGER NOT NULL REFERENCES drugs(drug_id),
    event_type   TEXT,           -- e.g. 'Respiratory Depression', 'Bleeding', 'Myopathy'
    severity     TEXT CHECK(severity IN ('Mild','Moderate','Severe','Life-threatening')),
    onset_date   TEXT,
    resolved     INTEGER DEFAULT 0,
    notes        TEXT
);

-- ──────────────────────────────────────────────────────────────
-- RISK SCORES LOG (computed by interaction_engine.py)
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS risk_scores (
    score_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER NOT NULL REFERENCES patients(patient_id),
    drug_a_id    INTEGER REFERENCES drugs(drug_id),
    drug_b_id    INTEGER REFERENCES drugs(drug_id),
    gene_id      INTEGER REFERENCES genes(gene_id),
    phenotype    TEXT,
    ddi_score    INTEGER,
    pgx_score    INTEGER,
    total_score  INTEGER,
    risk_tier    TEXT,
    computed_at  TEXT DEFAULT (datetime('now')),
    alerts_json  TEXT            -- JSON array of alert strings
);

-- ──────────────────────────────────────────────────────────────
-- SEED: Demo Interaction Data (Codeine + CYP2D6 PM scenario)
-- ──────────────────────────────────────────────────────────────

-- PGx annotations for Codeine / CYP2D6
INSERT OR IGNORE INTO pgx_annotations
    (drug_id, gene_id, phenotype, recommendation, evidence_level, dose_change_pct)
SELECT
    d.drug_id, g.gene_id,
    'PM',
    'AVOID codeine — CYP2D6 PM cannot convert codeine to morphine. Therapeutic failure risk. Use alternative analgesic.',
    'A', -100
FROM drugs d, genes g
WHERE d.generic_name = 'Codeine' AND g.symbol = 'CYP2D6';

INSERT OR IGNORE INTO pgx_annotations
    (drug_id, gene_id, phenotype, recommendation, evidence_level, dose_change_pct)
SELECT d.drug_id, g.gene_id,
    'IM',
    'Use lowest effective dose; monitor for therapeutic failure.',
    'A', -25
FROM drugs d, genes g
WHERE d.generic_name = 'Codeine' AND g.symbol = 'CYP2D6';

INSERT OR IGNORE INTO pgx_annotations
    (drug_id, gene_id, phenotype, recommendation, evidence_level, dose_change_pct)
SELECT d.drug_id, g.gene_id,
    'NM', 'Standard dosing.', 'A', 0
FROM drugs d, genes g
WHERE d.generic_name = 'Codeine' AND g.symbol = 'CYP2D6';

INSERT OR IGNORE INTO pgx_annotations
    (drug_id, gene_id, phenotype, recommendation, evidence_level, dose_change_pct)
SELECT d.drug_id, g.gene_id,
    'UM',
    'AVOID — FDA Black Box Warning. Ultrarapid conversion to morphine → respiratory depression risk.',
    'A', 0
FROM drugs d, genes g
WHERE d.generic_name = 'Codeine' AND g.symbol = 'CYP2D6';

-- Warfarin / CYP2C9 PGx
INSERT OR IGNORE INTO pgx_annotations
    (drug_id, gene_id, phenotype, recommendation, evidence_level, dose_change_pct)
SELECT d.drug_id, g.gene_id,
    '*1/*3', 'Reduce initial dose by 30-40%. Frequent INR monitoring.', 'A', -35
FROM drugs d, genes g
WHERE d.generic_name = 'Warfarin' AND g.symbol = 'CYP2C9';

-- Clopidogrel / CYP2C19 PGx
INSERT OR IGNORE INTO pgx_annotations
    (drug_id, gene_id, phenotype, recommendation, evidence_level, dose_change_pct)
SELECT d.drug_id, g.gene_id,
    'PM', 'AVOID clopidogrel. Use prasugrel or ticagrelor.', 'A', -100
FROM drugs d, genes g
WHERE d.generic_name = 'Clopidogrel' AND g.symbol = 'CYP2C19';

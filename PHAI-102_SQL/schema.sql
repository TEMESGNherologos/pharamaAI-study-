-- ============================================================
-- PHAI-102: SQL for Clinical Databases
-- Pharmacy Intelligence Platform — Relational Schema
-- Database: SQLite (compatible) / PostgreSQL
-- ============================================================

PRAGMA foreign_keys = ON;

-- ──────────────────────────────────────────────────────────────
-- DRUGS
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS drugs (
    drug_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    generic_name     TEXT    NOT NULL UNIQUE,
    brand_name       TEXT,
    drug_class       TEXT,                  -- e.g. 'Opioid Analgesic', 'Anticoagulant'
    route            TEXT,                  -- PO, IV, SC, etc.
    narrow_ti        INTEGER DEFAULT 0,     -- 1 = narrow therapeutic index
    controlled_sched TEXT,                  -- e.g. 'Schedule II'
    openfda_id       TEXT,                  -- OpenFDA application_number
    pharmgkb_id      TEXT,                  -- PharmGKB drug accession PA#
    created_at       TEXT    DEFAULT (datetime('now'))
);

-- ──────────────────────────────────────────────────────────────
-- GENES & VARIANTS
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS genes (
    gene_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL UNIQUE,       -- e.g. CYP2D6
    full_name   TEXT,
    chromosome  TEXT,
    strand      TEXT
);

CREATE TABLE IF NOT EXISTS variants (
    variant_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    gene_id      INTEGER NOT NULL REFERENCES genes(gene_id),
    rsid         TEXT,                      -- dbSNP rsID
    hgvs         TEXT,                      -- e.g. NM_000106.6:c.100C>T
    star_allele  TEXT,                      -- e.g. *2, *17
    effect_type  TEXT                       -- e.g. 'loss-of-function', 'gain-of-function'
);

-- ──────────────────────────────────────────────────────────────
-- PGx — Drug-Gene Annotations
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pgx_annotations (
    pgx_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id          INTEGER NOT NULL REFERENCES drugs(drug_id),
    gene_id          INTEGER NOT NULL REFERENCES genes(gene_id),
    phenotype        TEXT,                  -- PM, IM, NM, UM
    recommendation   TEXT,                  -- CPIC guideline recommendation text
    evidence_level   TEXT,                  -- A, B, C, D (CPIC levels)
    dose_change_pct  REAL,                  -- % change from standard dose
    pharmgkb_pa_id   TEXT                   -- PharmGKB annotation ID
);

-- ──────────────────────────────────────────────────────────────
-- DRUG-DRUG INTERACTIONS
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS drug_interactions (
    interaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_a_id        INTEGER NOT NULL REFERENCES drugs(drug_id),
    drug_b_id        INTEGER NOT NULL REFERENCES drugs(drug_id),
    severity         TEXT CHECK(severity IN ('Contraindicated','Major','Moderate','Minor')),
    mechanism        TEXT,                  -- e.g. 'CYP3A4 inhibition', 'additive QTc'
    management       TEXT,                  -- clinical action recommended
    evidence_source  TEXT,                  -- 'Micromedex', 'Drugs.com', 'FDA'
    CHECK (drug_a_id != drug_b_id)
);

-- ──────────────────────────────────────────────────────────────
-- DOSAGES
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dosages (
    dosage_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id          INTEGER NOT NULL REFERENCES drugs(drug_id),
    indication       TEXT,
    population       TEXT CHECK(population IN ('adult','pediatric','geriatric','renal','hepatic')),
    dose_mg_per_kg   REAL,
    max_single_dose  REAL,
    frequency        TEXT,                  -- 'q4h', 'q8h', 'once daily', etc.
    renal_adjust     INTEGER DEFAULT 1,     -- 1 = adjustment required
    crcl_threshold   REAL                   -- mL/min below which dose adjustment applies
);

-- ──────────────────────────────────────────────────────────────
-- PATIENTS (for capstone demo)
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS patients (
    patient_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    mrn              TEXT UNIQUE,           -- Medical Record Number (anonymised)
    age              INTEGER,
    sex              TEXT CHECK(sex IN ('M','F')),
    weight_kg        REAL,
    height_cm        REAL,
    serum_creatinine REAL
);

-- ──────────────────────────────────────────────────────────────
-- PATIENT GENOTYPES
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS patient_genotypes (
    genotype_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER NOT NULL REFERENCES patients(patient_id),
    gene_id      INTEGER NOT NULL REFERENCES genes(gene_id),
    diplotype    TEXT,                      -- e.g. '*1/*2'
    phenotype    TEXT                       -- e.g. 'IM'
);

-- ──────────────────────────────────────────────────────────────
-- PERFORMANCE INDEXES
-- ──────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_drugs_generic       ON drugs(generic_name);
CREATE INDEX IF NOT EXISTS idx_interactions_a      ON drug_interactions(drug_a_id);
CREATE INDEX IF NOT EXISTS idx_interactions_b      ON drug_interactions(drug_b_id);
CREATE INDEX IF NOT EXISTS idx_interactions_sev    ON drug_interactions(severity);
CREATE INDEX IF NOT EXISTS idx_pgx_drug            ON pgx_annotations(drug_id);
CREATE INDEX IF NOT EXISTS idx_pgx_gene            ON pgx_annotations(gene_id);
CREATE INDEX IF NOT EXISTS idx_pgx_phenotype       ON pgx_annotations(phenotype);
CREATE INDEX IF NOT EXISTS idx_variants_gene       ON variants(gene_id);
CREATE INDEX IF NOT EXISTS idx_variants_rsid       ON variants(rsid);
CREATE INDEX IF NOT EXISTS idx_pt_geno_patient     ON patient_genotypes(patient_id);

-- ──────────────────────────────────────────────────────────────
-- SEED DATA — Genes
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO genes (symbol, full_name, chromosome) VALUES
  ('CYP2D6',  'Cytochrome P450 2D6',                       '22'),
  ('CYP2C9',  'Cytochrome P450 2C9',                       '10'),
  ('CYP2C19', 'Cytochrome P450 2C19',                      '10'),
  ('CYP3A4',  'Cytochrome P450 3A4',                       '7'),
  ('CYP3A5',  'Cytochrome P450 3A5',                       '7'),
  ('VKORC1',  'Vitamin K Epoxide Reductase Complex 1',     '16'),
  ('SLCO1B1', 'Solute Carrier Organic Anion Transporter 1B1','12'),
  ('DPYD',    'Dihydropyrimidine Dehydrogenase',           '1'),
  ('TPMT',    'Thiopurine S-Methyltransferase',            '6'),
  ('UGT1A1',  'UDP Glucuronosyltransferase 1A1',           '2');

-- ──────────────────────────────────────────────────────────────
-- SEED DATA — Key Drugs
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO drugs (generic_name, drug_class, narrow_ti, pharmgkb_id) VALUES
  ('Codeine',        'Opioid Analgesic',      0, 'PA449088'),
  ('Warfarin',       'Anticoagulant',         1, 'PA451906'),
  ('Clopidogrel',    'Antiplatelet',          0, 'PA449053'),
  ('Tamoxifen',      'Antineoplastic',        0, 'PA451581'),
  ('Simvastatin',    'HMG-CoA Reductase Inh', 0, 'PA451363'),
  ('Omeprazole',     'Proton Pump Inhibitor', 0, 'PA450704'),
  ('Fluorouracil',   'Antimetabolite',        1, 'PA128406956'),
  ('Azathioprine',   'Immunosuppressant',     1, 'PA448413'),
  ('Irinotecan',     'Topoisomerase Inh',     1, 'PA450085'),
  ('Metoprolol',     'Beta Blocker',          0, 'PA450480'),
  ('Fluoxetine',     'SSRI Antidepressant',   0, 'PA449679'),
  ('Fluconazole',    'Antifungal',            0, 'PA449673'),
  ('Clarithromycin', 'Macrolide Antibiotic',  0, 'PA448967'),
  ('Aspirin',        'Antiplatelet / NSAID',  0, 'PA448488');

-- ──────────────────────────────────────────────────────────────
-- SEED DATA — Clinically Significant Drug Interactions
-- ──────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO drug_interactions (drug_a_id, drug_b_id, severity, mechanism, management, evidence_source)
SELECT
    da.drug_id, db.drug_id,
    'Major',
    'Fluoxetine strongly inhibits CYP2D6, blocking codeine bioactivation into morphine.',
    'Avoid combination. Select non-opioid or alternative analgesic.',
    'CPIC / FDA'
FROM drugs da, drugs db
WHERE da.generic_name = 'Codeine' AND db.generic_name = 'Fluoxetine';

INSERT OR IGNORE INTO drug_interactions (drug_a_id, drug_b_id, severity, mechanism, management, evidence_source)
SELECT
    da.drug_id, db.drug_id,
    'Major',
    'Omeprazole inhibits CYP2C19 bioactivation of clopidogrel, lowering active metabolite and antiplatelet efficacy.',
    'Avoid co-administration. Use pantoprazole or H2-blocker.',
    'FDA'
FROM drugs da, drugs db
WHERE da.generic_name = 'Clopidogrel' AND db.generic_name = 'Omeprazole';

INSERT OR IGNORE INTO drug_interactions (drug_a_id, drug_b_id, severity, mechanism, management, evidence_source)
SELECT
    da.drug_id, db.drug_id,
    'Major',
    'Fluconazole inhibits CYP2C9 metabolism of S-warfarin, causing severe INR elevation and bleeding risk.',
    'Reduce warfarin dose by 25-50% and monitor INR closely.',
    'Micromedex'
FROM drugs da, drugs db
WHERE da.generic_name = 'Warfarin' AND db.generic_name = 'Fluconazole';

INSERT OR IGNORE INTO drug_interactions (drug_a_id, drug_b_id, severity, mechanism, management, evidence_source)
SELECT
    da.drug_id, db.drug_id,
    'Contraindicated',
    'Clarithromycin strongly inhibits CYP3A4, dramatically elevating simvastatin AUC and risk of rhabdomyolysis.',
    'Contraindicated. Suspend simvastatin during macrolide therapy or choose azithromycin.',
    'FDA'
FROM drugs da, drugs db
WHERE da.generic_name = 'Simvastatin' AND db.generic_name = 'Clarithromycin';

INSERT OR IGNORE INTO drug_interactions (drug_a_id, drug_b_id, severity, mechanism, management, evidence_source)
SELECT
    da.drug_id, db.drug_id,
    'Major',
    'Additive antiplatelet and anticoagulant effects significantly elevate gastrointestinal and major bleeding risks.',
    'Monitor closely for signs of bleeding. Consider gastroprotection.',
    'Micromedex'
FROM drugs da, drugs db
WHERE da.generic_name = 'Warfarin' AND db.generic_name = 'Aspirin';


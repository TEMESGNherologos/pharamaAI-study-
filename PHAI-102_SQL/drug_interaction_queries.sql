-- ============================================================
-- PHAI-102: SQL for Clinical Databases
-- Drug-Drug Interaction Flagging Queries
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- Q1. All interactions for a specific drug (by name)
-- ──────────────────────────────────────────────────────────────

SELECT
    da.generic_name                         AS "Drug A",
    db.generic_name                         AS "Drug B",
    di.severity,
    di.mechanism,
    di.management
FROM drug_interactions di
JOIN drugs da ON da.drug_id = di.drug_a_id
JOIN drugs db ON db.drug_id = di.drug_b_id
WHERE
    da.generic_name = 'Warfarin'
    OR db.generic_name = 'Warfarin'
ORDER BY
    CASE di.severity
        WHEN 'Contraindicated' THEN 1
        WHEN 'Major'           THEN 2
        WHEN 'Moderate'        THEN 3
        WHEN 'Minor'           THEN 4
    END;


-- ──────────────────────────────────────────────────────────────
-- Q2. All CONTRAINDICATED pairs in the database
-- ──────────────────────────────────────────────────────────────

SELECT
    da.generic_name AS "Drug A",
    db.generic_name AS "Drug B",
    di.mechanism,
    di.evidence_source
FROM drug_interactions di
JOIN drugs da ON da.drug_id = di.drug_a_id
JOIN drugs db ON db.drug_id = di.drug_b_id
WHERE di.severity = 'Contraindicated'
ORDER BY da.generic_name, db.generic_name;


-- ──────────────────────────────────────────────────────────────
-- Q3. Polypharmacy flag — patients on ≥5 drugs with interactions
--     (Requires a patient_medications junction table in capstone)
-- ──────────────────────────────────────────────────────────────

/*
SELECT
    p.mrn,
    COUNT(DISTINCT pm.drug_id)     AS n_drugs,
    COUNT(DISTINCT di.interaction_id) AS n_interactions,
    GROUP_CONCAT(d.generic_name, ', ') AS drug_list
FROM patients p
JOIN patient_medications pm ON pm.patient_id = p.patient_id
JOIN drugs d ON d.drug_id = pm.drug_id
LEFT JOIN drug_interactions di
    ON  (di.drug_a_id = pm.drug_id OR di.drug_b_id = pm.drug_id)
GROUP BY p.patient_id
HAVING n_drugs >= 5 AND n_interactions > 0
ORDER BY n_interactions DESC;
*/


-- ──────────────────────────────────────────────────────────────
-- Q4. PGx risk report — drug + gene + phenotype + recommendation
-- ──────────────────────────────────────────────────────────────

SELECT
    d.generic_name                  AS drug,
    g.symbol                        AS gene,
    pa.phenotype,
    pa.evidence_level,
    pa.recommendation,
    pa.dose_change_pct
FROM pgx_annotations pa
JOIN drugs d ON d.drug_id = pa.drug_id
JOIN genes g ON g.gene_id = pa.gene_id
WHERE pa.evidence_level IN ('A', 'B')   -- high-confidence CPIC annotations
ORDER BY d.generic_name, pa.phenotype;


-- ──────────────────────────────────────────────────────────────
-- Q5. Narrow Therapeutic Index drugs with Major+ interactions
-- ──────────────────────────────────────────────────────────────

SELECT
    da.generic_name     AS "NTI Drug",
    db.generic_name     AS "Interacting Drug",
    di.severity,
    di.mechanism
FROM drug_interactions di
JOIN drugs da ON da.drug_id = di.drug_a_id
JOIN drugs db ON db.drug_id = di.drug_b_id
WHERE da.narrow_ti = 1
  AND di.severity IN ('Contraindicated', 'Major')
ORDER BY di.severity, da.generic_name;


-- ──────────────────────────────────────────────────────────────
-- Q6. CYP2D6 Poor Metabolizer — drugs needing dose reduction
-- ──────────────────────────────────────────────────────────────

SELECT
    d.generic_name,
    pa.dose_change_pct,
    pa.recommendation
FROM pgx_annotations pa
JOIN drugs d  ON d.drug_id  = pa.drug_id
JOIN genes g  ON g.gene_id  = pa.gene_id
WHERE g.symbol   = 'CYP2D6'
  AND pa.phenotype = 'PM'
  AND pa.dose_change_pct < 0          -- dose should be reduced
ORDER BY pa.dose_change_pct ASC;      -- most reduction first


-- ──────────────────────────────────────────────────────────────
-- Q7. Summary stats — interactions by severity class
-- ──────────────────────────────────────────────────────────────

SELECT
    severity,
    COUNT(*) AS total_pairs,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_all
FROM drug_interactions
GROUP BY severity
ORDER BY
    CASE severity
        WHEN 'Contraindicated' THEN 1
        WHEN 'Major'           THEN 2
        WHEN 'Moderate'        THEN 3
        WHEN 'Minor'           THEN 4
    END;


-- ──────────────────────────────────────────────────────────────
-- Q8. Full drug profile — joins drugs + dosages + PGx
-- ──────────────────────────────────────────────────────────────

SELECT
    d.generic_name,
    d.drug_class,
    d.narrow_ti,
    dos.indication,
    dos.population,
    dos.dose_mg_per_kg,
    dos.frequency,
    g.symbol                AS gene,
    pa.phenotype,
    pa.recommendation
FROM drugs d
LEFT JOIN dosages        dos ON dos.drug_id = d.drug_id
LEFT JOIN pgx_annotations pa ON pa.drug_id  = d.drug_id
LEFT JOIN genes          g   ON g.gene_id   = pa.gene_id
WHERE d.generic_name = 'Codeine'
ORDER BY dos.population, pa.phenotype;

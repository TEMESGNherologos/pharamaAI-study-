import sqlite3
import pandas as pd
from pathlib import Path

csv_path = Path("PHAI-102_SQL/clinical_pgx_report.csv")
db_path = Path("PHAI-102_SQL/clinic_db.sqlite")

print(f"Loading {csv_path}...")
df = pd.read_csv(csv_path)
print(f"Loaded {len(df)} rows, columns: {list(df.columns)}")

# Connect to clinic_db.sqlite
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Ingest full table clinical_pgx_report
df.to_sql("clinical_pgx_report", conn, if_exists="replace", index=False)
cursor.execute("CREATE INDEX IF NOT EXISTS idx_cpr_drug_name ON clinical_pgx_report(drug_name)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_cpr_gene_symbol ON clinical_pgx_report(gene_symbol)")

# 2. Update/Upsert into drugs table
cursor.execute("""
CREATE TABLE IF NOT EXISTS drugs (
    drug_id INTEGER PRIMARY KEY,
    drug_name TEXT UNIQUE,
    brand_name TEXT,
    active_ingredient TEXT,
    boxed_warning TEXT,
    indications TEXT
)
""")

for _, row in df.iterrows():
    cursor.execute("""
    INSERT INTO drugs (drug_id, drug_name, brand_name, active_ingredient, boxed_warning, indications)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(drug_id) DO UPDATE SET
        drug_name=excluded.drug_name,
        brand_name=excluded.brand_name,
        active_ingredient=excluded.active_ingredient,
        boxed_warning=excluded.boxed_warning,
        indications=excluded.indications
    """, (
        int(row["drug_id"]),
        str(row["drug_name"]) if pd.notna(row["drug_name"]) else None,
        str(row["brand_name"]) if pd.notna(row["brand_name"]) else None,
        str(row["active_ingredient"]) if pd.notna(row["active_ingredient"]) else None,
        str(row["boxed_warning"]) if pd.notna(row["boxed_warning"]) else None,
        str(row["indications"]) if pd.notna(row["indications"]) else None,
    ))

# 3. Check gene targets
gene_rows = df[df["gene_symbol"].notna()]
for _, row in gene_rows.iterrows():
    cursor.execute("""
    INSERT OR IGNORE INTO gene_targets (drug_name, gene_symbol, ncbi_id)
    VALUES (?, ?, ?)
    """, (
        row["drug_name"],
        row["gene_symbol"],
        str(row["ncbi_id"]) if pd.notna(row["ncbi_id"]) else None
    ))

conn.commit()

# Verification
cursor.execute("SELECT COUNT(*) FROM clinical_pgx_report")
print("Total rows in clinical_pgx_report table:", cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM drugs")
print("Total rows in drugs table:", cursor.fetchone()[0])

cursor.execute("SELECT drug_id, drug_name, brand_name, gene_symbol FROM clinical_pgx_report WHERE boxed_warning != 'None' LIMIT 3")
print("Sample drugs with boxed warnings:")
for r in cursor.fetchall():
    print("  -", r)

conn.close()

# Also sync to capstone database if present
capstone_db = Path("capstone/database/pharmacy_intelligence.db")
if capstone_db.exists():
    c_conn = sqlite3.connect(capstone_db)
    df.to_sql("clinical_pgx_report", c_conn, if_exists="replace", index=False)
    c_conn.commit()
    c_conn.close()
    print(f"Synced clinical_pgx_report table into {capstone_db}.")

print("Ingestion completed successfully!")

from pathlib import Path
import sqlite3
import pandas as pd

# 1. Coordinate Pathlib routing relative to the script location
script_path = Path(__file__).resolve()
project_dir = script_path.parent
base_dir = project_dir.parent
databases_dir = base_dir / "databases"
project_db_path = databases_dir / "ag_project_analysis.db"

print("Connecting to project sandbox database...")
with sqlite3.connect(project_db_path) as conn:
    # We pull ONLY the training pool (is_oos = 0) to preserve the integrity of our test set
    query = "SELECT * FROM ag_ecosystem_cohort WHERE is_oos = 0;"
    print("Loading co-temporal training pool into memory...")
    df = pd.read_sql_query(query, conn)

print(f"Successfully loaded {len(df):,} training loans. Starting audit...\n")

# =====================================================================
# AUDIT PART 1: Business Age Structure
# =====================================================================
print("=" * 60)
print("AUDIT PART 1: BUSINESS AGE FIELD PROFILES")
print("=" * 60)

for col in ["businessage", "business_age_proxy"]:
    print(f"\nDistribution for column: '{col}'")
    print("-" * 40)
    # Calculate counts including missing data
    counts = df[col].value_counts(dropna=False)
    pcts = df[col].value_counts(dropna=False, normalize=True) * 100

    dist_df = pd.DataFrame({"Loan Count": counts, "Percentage": pcts.round(2)})
    print(dist_df)

# =====================================================================
# AUDIT PART 2: 4-Digit NAICS Density Profile
# =====================================================================
print("\n" + "=" * 60)
print("AUDIT PART 2: TOP 15 CORE 4-DIGIT NAICS CODES")
print("=" * 60)

naics_counts = df["naics_4_digit"].value_counts()
naics_pcts = df["naics_4_digit"].value_counts(normalize=True) * 100

naics_df = pd.DataFrame(
    {"Loan Count": naics_counts, "Percentage": naics_pcts.round(2)}
).head(15)

print(naics_df)

# =====================================================================
# AUDIT PART 3: Matrix Cross-Tabulation (NAICS x Age Proxy)
# =====================================================================
print("\n" + "=" * 60)
print("AUDIT PART 3: TOP 4-DIGIT NAICS BY BUSINESS AGE PROXY")
print("=" * 60)

# Get the list of the top 8 most frequent 4-digit codes to keep the matrix clean
top_8_naics = df["naics_4_digit"].value_counts().head(8).index

# Filter dataframe down to just the top sectors for clean viewing
df_top_sectors = df[df["naics_4_digit"].isin(top_8_naics)]

# Run a cross-tabulation matrix
matrix = pd.crosstab(
    index=df_top_sectors["naics_4_digit"],
    columns=df_top_sectors["business_age_proxy"].fillna("MISSING/NULL"),
    margins=True,
    margins_name="Total Pool",
)

print(matrix.to_string())
print("\n=== DATA AUDIT COMPLETE ===")

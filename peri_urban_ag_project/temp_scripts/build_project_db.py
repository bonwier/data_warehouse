from pathlib import Path
import sqlite3
import sys
import pandas as pd
import numpy as np

# 1. Coordinate Pathlib Routing and Append Utils to the Sys Path
# Script location: data_warehouse/peri_urban_ag_project/build_project_db.py
script_path = Path(__file__).resolve()
project_dir = script_path.parent
base_dir = project_dir.parent
databases_dir = base_dir / "databases"
utils_dir = base_dir / "utils"

# Inject the master root directory into sys.path so Python can find 'utils'
if str(base_dir) not in sys.path:
    sys.path.append(str(base_dir))

# Now this import works perfectly everywhere
from utils.geography_daemon import GeographyDaemon

master_db_path = databases_dir / "sba_7a_analysis.db"
project_db_path = databases_dir / "ag_project_analysis.db"

# 2. In-Memory Extraction from Master Database
print("Connecting to master database...")
with sqlite3.connect(master_db_path) as master_conn:
    # Explicitly pull transaction fields required to build our Capital Structure Proxies
    # Note: We completely omit your old "business_age_proxy" and "standardized_fips" fields
    query = """
        SELECT 
            terminmonths, isdefaulted, naicscode, naics2digit, approvalfy,
            borrzip, borrstate, projectcounty, grossapproval
        FROM model_cohort_2003_present
        WHERE (
            naics2digit = '11' 
            OR CAST(naicscode AS TEXT) LIKE '311%' 
            OR CAST(naicscode AS TEXT) LIKE '4244%'
        )
        AND CAST(naicscode AS TEXT) NOT LIKE '112320%'   -- Exclude poultry noise
        AND CAST(naicscode AS TEXT) NOT LIKE '1133%';    -- Exclude logging noise
    """
    print("Loading target agricultural ecosystem records into RAM...")
    df = pd.read_sql_query(query, master_conn)

print(f"Loaded {len(df):,} matching loans. Engineering Capital Structures...")

# 3. Build the Objective Capital Structure Proxies (Shedding Calendar Age)
# Track structural elements: Term structure and Leverage Type
df["naics_4_digit"] = df["naicscode"].astype(str).str[:4]

# A) Term Structure Classification
term_conditions = [
    (df["terminmonths"] <= 36),
    (df["terminmonths"] > 36) & (df["terminmonths"] <= 84),
]
term_choices = ["SHORT_TERM", "MED_TERM"]
df["term_structure"] = np.select(term_conditions, term_choices, default="LONG_TERM")

# B) Capital Transaction Structure (Replacing your old Startup/Early-stage definitions)
# High-Exposure Capital = Long amortizations combined with standard max infrastructure funding
# Working Lines = Very compressed cash lines vulnerable to immediate disruptions
cap_conditions = [
    (df["term_structure"] == "SHORT_TERM"),
    (df["term_structure"] == "LONG_TERM") & (df["grossapproval"] >= 500000),
]
cap_choices = ["WORKING_LINE_EXPOSURE", "HIGH_INFRASTRUCTURE_EXPOSURE"]
df["capital_structure_proxy"] = np.select(
    cap_conditions, cap_choices, default="STANDARD_COMMERCIAL_EXPOSURE"
)

# 4. Integrate your Native GeographyDaemon to resolve FIPS mapping
print("Initializing GeographyDaemon interface...")
daemon = GeographyDaemon(database_dir=databases_dir)

print("Running two-tier sequential spatial daemon over dataframe...")
df = daemon.attach_fips_to_sba_dataframe(
    df=df,
    zip_col="borrzip",
    state_col="borrstate",
    county_col="projectcounty",
    year_col="approvalfy",
    output_col="project_fips_clean",
)
daemon.close()

# 5. Execute Co-Temporal Random Partition
print("Generating reproducible 80/20 train/test split...")
rng = np.random.default_rng(seed=42)
df["is_oos"] = rng.choice([0, 1], size=len(df), p=[0.80, 0.20])

# 6. Write New Project Database
print(f"Writing pristine data workspace to disk: {project_db_path.name}...")
with sqlite3.connect(project_db_path) as project_conn:
    new_table_name = "ag_ecosystem_cohort"
    df.to_sql(new_table_name, project_conn, if_exists="replace", index=False)

    print("Optimizing database table indexing structures...")
    cursor = project_conn.cursor()
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_proj_naics ON {new_table_name}(naics_4_digit);"
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_proj_oos ON {new_table_name}(is_oos);"
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_proj_fips ON {new_table_name}(project_fips_clean);"
    )
    project_conn.commit()

train_size = len(df[df["is_oos"] == 0])
test_size = len(df[df["is_oos"] == 1])

print("\n=== DATA WORKSPACE SECURELY BULLETPROOFED VIA GEOGRAPHY DAEMON ===")
print(f"  * Co-Temporal Training Pool (80%): {train_size:,} records")
print(f"  * Co-Temporal Testing Shield (20%): {test_size:,} records")
print(f"  * Complete Calibrated Volume:        {len(df):,} records")

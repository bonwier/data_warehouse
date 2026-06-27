from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
from lifelines import CoxPHFitter

# 1. Coordinate Pathlib Routing
script_path = Path(__file__).resolve()
project_dir = script_path.parent
base_dir = project_dir.parent
databases_dir = base_dir / "databases"
project_db_path = databases_dir / "ag_project_analysis.db"

# 2. Load the Training Array directly into RAM
print("Connecting to project sandbox database...")
with sqlite3.connect(project_db_path) as conn:
    # Pulling columns required for the hazard analysis and economic hooks
    query = """
        SELECT 
            terminmonths, 
            isdefaulted, 
            business_age_proxy, 
            naics_4_digit,
            standardized_fips
        FROM ag_ecosystem_cohort
        WHERE is_oos = 0
          AND naics_4_digit IN ('3118', '4244');
    """
    print("Loading target training array into RAM...")
    df = pd.read_sql_query(query, conn)

print(f"Loaded {len(df):,} loans. Engineering structural controls...")

# 3. Resolve the Term Length Contamination (Binning Maturity)
# This prevents short-term lines from distorting our long-term asset curves
conditions = [
    (df["terminmonths"] <= 36),
    (df["terminmonths"] > 36) & (df["terminmonths"] <= 84),
]
choices = ["SHORT_TERM", "MED_TERM"]
df["term_structure"] = np.select(conditions, choices, default="LONG_TERM")

# Mocking illustrative proxy columns for your BLS/IRS economic indicators
# (Since we are keeping it self-contained within this database layer for now)
# Replace these with your actual database join logic when ready!
df["local_unemployment_rate"] = np.random.uniform(3.0, 12.0, len(df))
df["local_income_growth_pct"] = np.random.uniform(-5.0, 15.0, len(df))

# 4. Configure and Execute the Stratified Cox Engine
print("\nInitializing Stratified Cox Proportional Hazards Engine...")
cph = CoxPHFitter()

# We STRATIFY by Industry, Age Proxy, and Term Structure.
# This builds completely independent hazard curves for every unique profile cell.
# The macro economic continuous variables act as multipliers on top of those baselines.
cph.fit(
    df,
    duration_col="terminmonths",
    event_col="isdefaulted",
    formula="local_unemployment_rate + local_income_growth_pct",
    strata=["naics_4_digit", "business_age_proxy", "term_structure"],
)

# Print out the complete statistical breakdown of the risk dials
cph.print_summary()

# 6. Extract and Save the Baseline Hazard Staircases
# This generates a matrix of the core curves that you will use for pricing.
baseline_matrices = cph.baseline_cumulative_hazard_
output_csv = project_dir / "engineered_pricing_staircases.csv"
baseline_matrices.to_csv(output_csv)

print(f"\n[SUCCESS] Baseline pricing staircases exported to: {output_csv.name}")
print("=== PORTFOLIO MODEL TRAINING COMPLETE ===")

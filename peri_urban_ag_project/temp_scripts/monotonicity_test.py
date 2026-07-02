from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
from lifelines import NelsonAalenFitter

# 1. Coordinate Pathlib Routing
script_path = Path(__file__).resolve()
project_dir = script_path.parent
base_dir = project_dir.parent
databases_dir = base_dir / "databases"
project_db_path = databases_dir / "ag_project_analysis.db"

print("Connecting to project sandbox database...")
with sqlite3.connect(project_db_path) as conn:
    # Pull only the training pool data (is_oos == 0)
    query = """
        SELECT 
            terminmonths, 
            isdefaulted, 
            naics_4_digit,
            capital_structure_proxy
        FROM ag_ecosystem_cohort
        WHERE is_oos = 0
          AND naics_4_digit IN ('3118', '4244');
    """
    df = pd.read_sql_query(query, conn)

print(f"Loaded {len(df):,} training records. Running Layer 1 Monotonicity Audit...")

# 2. Initialize the Nelson-Aalen Non-Parametric Hazard Estimator
naf = NelsonAalenFitter()

# We track risk accumulation at key operational milestones (Years 1, 3, 5, 7)
milestones = [12, 36, 60, 84]

print("\n" + "=" * 90)
print(
    "LAYER 1 MONOTONICITY MATRIX: CUMULATIVE HAZARD ACCUMULATION BY OPERATIONAL MILESTONE"
)
print("=" * 90)

# 3. Iterate through Strata to check for risk ordering
for industry in sorted(df["naics_4_digit"].unique()):
    print(f"\nINDUSTRY PROFILE: NAICS {industry}")
    print("-" * 90)
    df_ind = df[df["naics_4_digit"] == industry]

    matrix_data = []

    for proxy in [
        "WORKING_LINE_EXPOSURE",
        "STANDARD_COMMERCIAL_EXPOSURE",
        "HIGH_INFRASTRUCTURE_EXPOSURE",
    ]:
        df_cell = df_ind[
            df_ind["capital_structure_proxy"] == proxy
        ]  # <-- Changed 'group' to 'proxy'

        if len(df_cell) < 30:
            # Shield against unstable estimations from sparse cells
            continue

        # Fit the empirical, un-biased hazard curve
        naf.fit(
            durations=df_cell["terminmonths"], event_observed=df_cell["isdefaulted"]
        )

        # Extract hazard values at milestones, handle missing points via forward-fill
        cum_hazards = naf.cumulative_hazard_
        row_metrics = {"Proxy_Tier": proxy, "Sample_Size": len(df_cell)}

        for m in milestones:
            # Find closest available operational month in the fitted curve index
            closest_month = cum_hazards.index[np.abs(cum_hazards.index - m).argmin()]
            row_metrics[f"Month_{m}_Haz"] = round(
                float(cum_hazards.loc[closest_month].iloc[0]), 4
            )

        matrix_data.append(row_metrics)

    # Display the resulting text matrix for the industry block
    df_results = pd.DataFrame(matrix_data)
    if not df_results.empty:
        print(df_results.to_string(index=False))
    else:
        print("  [WARNING] Insufficient data density to map this industry profile.")

print("=" * 90)
print("\n=== MONOTONICITY AUDIT COMPLETE ===")

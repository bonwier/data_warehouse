from pathlib import Path
import sqlite3
import pandas as pd

# 1. Coordinate Pathlib Routing
script_path = Path(__file__).resolve()
project_dir = script_path.parent
base_dir = project_dir.parent
databases_dir = base_dir / "databases"
project_db_path = databases_dir / "ag_project_analysis.db"

print("Connecting to project sandbox database...")
with sqlite3.connect(project_db_path) as conn:
    # 2. Extract loans that actually defaulted, tracking industry, term structure, and timeline
    # Note: Using your master 'chargeoffdate' or 'isdefaulted' field relative to maturity
    query = """
        SELECT 
            naics_4_digit,
            term_structure,
            isdefaulted,
            terminmonths
        FROM ag_ecosystem_cohort
        WHERE is_oos = 0;
    """
    df = pd.read_sql_query(query, conn)

print(f"Loaded training pool metrics. Analyzing default horizons...")

# Filter down strictly to the loans that experienced a failure event
df_defaults = df[df["isdefaulted"] == 1].copy()

# 3. Establish our chronological distribution buckets (12, 36, and 60 months)
time_buckets = [12, 36, 60]

print("\n" + "=" * 95)
print("EXACT PORTFOLIO DEFAULT DISTRIBUTION SHARE BY FACILITY TIER")
print("=" * 95)

for tier in ["SHORT_TERM", "MED_TERM", "LONG_TERM"]:
    print(f"\nFACILITY TIER: {tier}")
    print("-" * 95)
    df_tier = df_defaults[df_defaults["term_structure"] == tier]

    if df_tier.empty:
        print("  [INFO] No default events observed in this structural asset tier.")
        continue

    for months in time_buckets:
        # Isolate defaults that hit within the specific milestone window
        df_window = df_tier[df_tier["terminmonths"] <= months]

        if df_window.empty:
            continue

        print(
            f"\n  * Chronological Default Window: Within First {months} Months (Total Defaults = {len(df_window)})"
        )

        # Calculate the absolute percentage breakdown by industry sector
        counts = df_window["naics_4_digit"].value_counts()
        pcts = df_window["naics_4_digit"].value_counts(normalize=True) * 100

        dist_df = pd.DataFrame(
            {
                "Industry_4_Digit": counts.index,
                "Default_Count": counts.values,
                "Share_Of_Tier_Pct": pcts.values.round(2),
            }
        )
        print(dist_df.to_string(index=False))

print("=" * 95)
print("\n=== DISTRIBUTION RUN COMPLETE ===")

from pathlib import Path
import sqlite3
import pandas as pd

# 1. Coordinate Pathlib routing relative to script location
script_path = Path(__file__).resolve()
project_dir = script_path.parent
base_dir = project_dir.parent
databases_dir = base_dir / "databases"
project_db_path = databases_dir / "ag_project_analysis.db"

print(f"Connecting to project database at: {project_db_path.name}")
with sqlite3.connect(project_db_path) as conn:
    # 2. Build a granular text matrix grouping by industry, age proxy, and time blocks
    # This categorizes loans into 2-year operational risk windows based on terminmonths
    query = """
        SELECT 
            naics_4_digit AS Industry,
            business_age_proxy AS Age_Proxy,
            CASE 
                WHEN terminmonths <= 24 THEN '01-24 Months (Grace Period)'
                WHEN terminmonths <= 48 THEN '25-48 Months (Valley of Death)'
                WHEN terminmonths <= 72 THEN '49-72 Months (Scaling Phase)'
                ELSE '73+ Months (Mature Plateau)'
            END AS Operational_Window,
            COUNT(*) AS Total_Loans,
            SUM(isdefaulted) AS Total_Defaults,
            ROUND(AVG(isdefaulted) * 100, 2) AS Default_Rate_Pct
        FROM ag_ecosystem_cohort
        WHERE is_oos = 0
          AND naics_4_digit IN ('3118', '4244')
        GROUP BY Industry, Age_Proxy, Operational_Window
        ORDER BY Industry, Age_Proxy, Operational_Window;
    """

    print("Aggregating historical hazard matrices in memory...")
    df_matrix = pd.read_sql_query(query, conn)

# 3. Print out a clean, scannable data frame directly to the console
print("\n" + "=" * 85)
print("HISTORICAL HAZARD DISTRIBUTION MATRIX (TRAINING COHORT)")
print("=" * 85)
print(df_matrix.to_string(index=False))
print("=" * 85)
print("\n=== DATA EXTRACTION COMPLETE ===")

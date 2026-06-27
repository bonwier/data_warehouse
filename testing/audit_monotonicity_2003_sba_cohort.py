import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np


def main():
    SCRIPT_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = SCRIPT_DIR.parent
    DB_PATH = PROJECT_ROOT / "databases" / "sba_7a_analysis.db"

    if not DB_PATH.exists():
        print(f"ERROR: Database missing at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    print(
        "--- Auditing Monotonicity Over Equivalent Exposure Windows (First 36 Months) ---"
    )
    print("Extracting variables for in-memory datetime parsing...")

    query = """
    SELECT 
        business_age_proxy,
        approvaldate,
        chargeoffdate,
        isdefaulted
    FROM model_cohort_2003_present;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # 1. Force robust date conversion handling slashes natively
    df["dt_approval"] = pd.to_datetime(df["approvaldate"], errors="coerce")
    df["dt_chargeoff"] = pd.to_datetime(df["chargeoffdate"], errors="coerce")

    # Snapshot fallback anchor date matching your database build specifications
    SNAPSHOT_DATE = pd.to_datetime("2026-03-31")

    # If a loan defaulted, terminal date is the chargeoff. If active, terminal date is snapshot wall.
    df["dt_terminal"] = np.where(
        df["dt_chargeoff"].notna(), df["dt_chargeoff"], SNAPSHOT_DATE
    )

    # 2. Compute true lifespan in calendar months
    df["exposure_months"] = (
        df["dt_terminal"].dt.year - df["dt_approval"].dt.year
    ) * 12 + (df["dt_terminal"].dt.month - df["dt_approval"].dt.month)

    # 3. Apply strict actuarial filtering rules
    # An early default occurs if the loan defaulted AND it failed within the first 36 months of exposure.
    df["is_early_default"] = np.where(
        (df["isdefaulted"] == 1) & (df["exposure_months"] <= 36), 1, 0
    )

    # 4. Group and aggregate distributions
    summary = (
        df.groupby("business_age_proxy")
        .agg(
            total_eligible_loans=("business_age_proxy", "count"),
            early_defaults=("is_early_default", "sum"),
        )
        .reset_index()
    )

    summary["early_default_rate_pct"] = np.round(
        (summary["early_defaults"] * 100.0) / summary["total_eligible_loans"], 2
    )
    summary = summary.sort_values(by="early_default_rate_pct", ascending=True)

    print("\n--- TRANSFORMATIVE 36-MONTH EXPOSURE PROFILES ---")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

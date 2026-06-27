import sqlite3
from pathlib import Path
import pandas as pd


def main():
    ROOT_DIR = Path(__file__).resolve().parent.parent
    DB_PATH = ROOT_DIR / "databases" / "sba_7a_analysis.db"
    TABLE_NAME = "sba_7a_loans"

    if not DB_PATH.exists():
        print(f"ERROR: Database missing at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    print("--- Running Longitudinal Business Age Proxy Analysis ---")

    # Query 1: Cross-Tabulation of Proxy Tag by Structural Policy Era
    era_query = f"""
    SELECT 
        CASE 
            WHEN approvalfy <= 1995 THEN '1. Pre-Zero-Subsidy (1991-1995)'
            WHEN approvalfy <= 2001 THEN '2. Standard Fees (1996-2001)'
            WHEN approvalfy <= 2008 THEN '3. Post-9/11 Relaxed (2002-2008)'
            WHEN approvalfy <= 2011 THEN '4. ARRA High-Guarantee (2009-2011)'
            ELSE '5. Modern & Post-2018 (2012-Present)'
        END as policy_era,
        business_age_proxy,
        COUNT(*) as loan_count,
        ROUND(AVG(isdefaulted) * 100, 2) as default_rate_pct,
        ROUND(AVG(grossapproval)) as avg_loan_size
    FROM {TABLE_NAME}
    GROUP BY policy_era, business_age_proxy
    ORDER BY policy_era ASC, loan_count DESC;
    """

    df_era = pd.read_sql_query(era_query, conn)

    print("\n--- DISTRIBUTION AND RISK PROFILES BY POLICY ERA ---")
    print(df_era.to_string(index=False))

    # Query 2: Check on how the Missing NAICS cohort interacts with your age proxies
    garbage_strata_query = f"""
    SELECT 
        CASE WHEN naics2digit = '00' THEN 'MISSING NAICS (Garbage Stratum)' ELSE 'VALID NAICS SECTOR' END as naics_status,
        business_age_proxy,
        COUNT(*) as loan_count,
        ROUND(AVG(isdefaulted) * 100, 2) as default_rate_pct
    FROM {TABLE_NAME}
    GROUP BY naics_status, business_age_proxy
    ORDER BY naics_status DESC, loan_count DESC;
    """

    df_garbage = pd.read_sql_query(garbage_strata_query, conn)
    print("\n--- PROXIES INSIDE UNKNOWN VS VALID NAICS COHORTS ---")
    print(df_garbage.to_string(index=False))

    conn.close()
    print("\n--- Profiling Complete ---")


if __name__ == "__main__":
    main()

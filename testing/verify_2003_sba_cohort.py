import sqlite3
from pathlib import Path
import pandas as pd


def main():
    # 1. Coordinate Paths relative to testing directory location
    SCRIPT_DIR = Path(__file__).resolve().parent  # testing
    PROJECT_ROOT = SCRIPT_DIR.parent  # data_warehouse
    DB_PATH = PROJECT_ROOT / "databases" / "sba_7a_analysis.db"

    if not DB_PATH.exists():
        print(f"[FATAL] Core database missing at location: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    print("--- Executing Committed Warehouse Integrity Suite (FY2003+) ---")

    # Check total volume of the modeling cohort
    total_cohort_count = conn.execute(
        "SELECT COUNT(*) FROM model_cohort_2003_present;"
    ).fetchone()[0]
    print(f"Total Active Modeling Cohort Rows: {total_cohort_count:,}\n")

    # --------------------------------------------------------------------
    # TEST 1: Distribution of Business Age Proxies
    # --------------------------------------------------------------------
    print("=== [TEST 1] DISTRIBUTION OF BUSINESS AGE PROXIES ===")
    proxy_query = """
    SELECT 
        business_age_proxy,
        COUNT(*) as record_count,
        ROUND((COUNT(*) * 100.0) / (SELECT COUNT(*) FROM model_cohort_2003_present), 2) as percentage,
        ROUND(AVG(isdefaulted) * 100, 2) as default_rate_pct,
        ROUND(AVG(grossapproval)) as avg_loan_size
    FROM model_cohort_2003_present
    GROUP BY business_age_proxy
    ORDER BY record_count DESC;
    """
    df_proxy = pd.read_sql_query(proxy_query, conn)
    print(df_proxy.to_string(index=False))
    print("\n" + "=" * 60 + "\n")

    # --------------------------------------------------------------------
    # TEST 2: Missing NAICS Deep-Dive (Is it Random?)
    # --------------------------------------------------------------------
    print("=== [TEST 2] MISSING/INVALID NAICS COHORT PROFILE ===")

    # Calculate exactly where missing codes sit across your proxies
    missing_naics_query = """
    SELECT 
        business_age_proxy,
        COUNT(*) as missing_naics_count,
        ROUND(AVG(isdefaulted) * 100, 2) as default_rate_pct,
        ROUND(AVG(grossapproval)) as avg_loan_size
    FROM model_cohort_2003_present
    WHERE naicscode IS NULL OR naicscode = '' OR naics2digit = '00'
    GROUP BY business_age_proxy;
    """
    df_missing = pd.read_sql_query(missing_naics_query, conn)
    total_missing_naics = df_missing["missing_naics_count"].sum()
    print(
        f"Total Missing/Invalid NAICS records in 2003+ cohort: {total_missing_naics:,}"
    )
    print(
        f"Percentage of total cohort: {((total_missing_naics / total_cohort_count) * 100):.2f}%\n"
    )
    print("Distribution of Missing NAICS by Business Age Proxy:")
    print(df_missing.to_string(index=False))

    # Check chronological distribution of missing NAICS to test randomness
    print("\nChronological distribution of missing NAICS (Top 5 Years):")
    missing_years_query = """
    SELECT approvalfy, COUNT(*) as missing_count
    FROM model_cohort_2003_present
    WHERE naicscode IS NULL OR naicscode = '' OR naics2digit = '00'
    GROUP BY approvalfy
    ORDER BY missing_count DESC
    LIMIT 5;
    """
    df_missing_years = pd.read_sql_query(missing_years_query, conn)
    print(df_missing_years.to_string(index=False))
    print("\n" + "=" * 60 + "\n")

    # --------------------------------------------------------------------
    # TEST 3: Spatial Crosswalk Coverage Audit (Sanity Check)
    # --------------------------------------------------------------------
    print("=== [TEST 3] SPATIAL CROSSWALK COVERAGE SANITY CHECK ===")
    spatial_query = """
    SELECT 
        COUNT(*) as total_loans,
        SUM(CASE WHEN standardized_fips IS NULL OR standardized_fips = '' THEN 1 ELSE 0 END) as unmapped_spatial_loans,
        ROUND((SUM(CASE WHEN standardized_fips IS NULL OR standardized_fips = '' THEN 1.0 ELSE 0.0 END) * 100.0) / COUNT(*), 4) as spatial_leakage_pct
    FROM model_cohort_2003_present;
    """
    df_spatial = pd.read_sql_query(spatial_query, conn)
    print(df_spatial.to_string(index=False))
    print("\n" + "=" * 60 + "\n")

    # --------------------------------------------------------------------
    # TEST 4: Micro-Loan Boundary Threshold Check (Sanity Check)
    # --------------------------------------------------------------------
    print("=== [TEST 4] MICRO-LOAN BOUNDARY CLUSTERING SANE AUDIT ===")
    # Verifies if lenders are artificially manipulating loan sizes under the $150k fee waiver threshold
    fee_threshold_query = """
    SELECT 
        approvalfy,
        COUNT(CASE WHEN grossapproval >= 140000 AND grossapproval < 150000 THEN 1 END) as counts_140k_to_150k,
        COUNT(CASE WHEN grossapproval >= 150000 AND grossapproval <= 160000 THEN 1 END) as counts_150k_to_160k
    FROM model_cohort_2003_present
    WHERE approvalfy IN (2014, 2015, 2016)
    GROUP BY approvalfy;
    """
    df_threshold = pd.read_sql_query(fee_threshold_query, conn)
    print("Evaluating expected regulatory clustering around the $150,000 fee barrier:")
    print(df_threshold.to_string(index=False))

    conn.close()
    print("\n--- Integrity Suite Complete ---")


if __name__ == "__main__":
    main()

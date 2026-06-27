# data_warehouse/testing/audit_bls_integrity.py
import sqlite3
from pathlib import Path
import pandas as pd


def run_bls_integrity_suite(bls_db_path: Path, spatial_db_path: Path):
    """Executes structural, chronological, and spatial audits against the BLS database."""
    print("[*] Initializing BLS Macro Warehouse Integrity Suite...")

    bls_conn = sqlite3.connect(bls_db_path)
    spatial_conn = sqlite3.connect(spatial_db_path)

    try:
        # -------------------------------------------------------------------------
        # AUDIT 1: Chronological Continuity (Filtering Out Non-Standard N0 Codes)
        # -------------------------------------------------------------------------
        print(
            "[*] Audit 1: Scanning for chronological reporting gaps (Standard Counties)..."
        )

        # Enforce numeric state FIPS check to skip 'N0' regional composite territories
        # Restrict the evaluation to historical years (< 2026) to avoid false lag alarms
        continuity_query = """
            SELECT state_fips, county_fips, year, COUNT(DISTINCT period) as month_count
            FROM laus_monthly_records
            WHERE period >= 'M01' AND period <= 'M12'
              AND year < 2026
              AND state_fips NOT LIKE 'N%'
            GROUP BY state_fips, county_fips, year
            HAVING month_count != 12;
        """
        gaps_df = pd.read_sql_query(continuity_query, bls_conn)

        if not gaps_df.empty:
            print(
                f"[!] WARNING: Found {len(gaps_df):,} instances of historical county reporting gaps."
            )
            print(gaps_df.head(10))
        else:
            print(
                "[+] Success: All standard historical county-vintages contain 12 complete months."
            )

        # -------------------------------------------------------------------------
        # AUDIT 2: Spatial Crosswalk Realignment (dim_geography_fips Match)
        # -------------------------------------------------------------------------
        print("[*] Audit 2: Testing spatial alignment against dim_geography_fips...")

        # Combine state_fips and county_fips to match the 5-character standardized layout
        bls_fips_query = """
            SELECT DISTINCT (state_fips || county_fips) AS fips 
            FROM laus_monthly_records
            WHERE state_fips NOT LIKE 'N%';
        """
        bls_fips = pd.read_sql_query(bls_fips_query, bls_conn)["fips"].dropna().unique()

        # Pull valid, master FIPS directly from your dimensional geography table
        spatial_fips_query = (
            "SELECT DISTINCT standardized_fips FROM dim_geography_fips;"
        )
        spatial_fips = (
            pd.read_sql_query(spatial_fips_query, spatial_conn)["standardized_fips"]
            .dropna()
            .unique()
        )

        # Isolate entries present in BLS data that are missing from your master registry
        unmapped_fips = set(bls_fips) - set(spatial_fips)

        if unmapped_fips:
            print(
                f"[!] WARNING: Found {len(unmapped_fips)} FIPS codes in BLS missing from dim_geography_fips."
            )
            print(f"[-] Sample unmapped codes: {sorted(list(unmapped_fips))[:10]}")
        else:
            print(
                "[+] Success: 100% of standard BLS records map cleanly to dim_geography_fips."
            )

        # -------------------------------------------------------------------------
        # AUDIT 3: Actuarial Boundary Test (Unemployment Rate Bounds)
        # -------------------------------------------------------------------------
        print(
            "[*] Audit 3: Checking boundary constraints on measure '03' (Unemployment Rate)..."
        )

        boundary_query = """
            SELECT COUNT(*) as anomaly_count, MIN(value) as min_val, MAX(value) as max_val
            FROM laus_monthly_records
            WHERE measure_code = '03' AND (value < 0.0 OR value > 50.0);
        """
        bounds_df = pd.read_sql_query(boundary_query, bls_conn)
        anomaly_count = bounds_df["anomaly_count"].iloc[0]

        if anomaly_count > 0:
            print(
                f"[!] CRITICAL: Found {anomaly_count} unemployment records tracking outside logical 0-50% bounds."
            )
            print(
                f"[-] Range observed: {bounds_df['min_val'].iloc[0]}% to {bounds_df['max_val'].iloc[0]}%"
            )
        else:
            print(
                "[+] Success: All audited unemployment metrics fall within standard operational bounds."
            )

    finally:
        bls_conn.close()
        spatial_conn.close()

    print("[+] Audit suite run complete.")


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent.parent

    DB_BLS = BASE_DIR / "databases" / "bls_laus_macro.db"
    DB_SPATIAL = BASE_DIR / "databases" / "spatial_crosswalk.db"

    run_bls_integrity_suite(DB_BLS, DB_SPATIAL)

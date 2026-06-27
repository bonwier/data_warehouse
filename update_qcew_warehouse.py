import sqlite3
import re
import pandas as pd
from pathlib import Path

# ==================================================================== #
# DETECT ROOT ENVIRONMENT PATHS                                       #
# ==================================================================== #
ROOT_DIR = Path(__file__).resolve().parent
QCEW_TARGET_DIR = ROOT_DIR / "raw_datasets" / "bls" / "qcew_zips"
QCEW_DB_PATH = ROOT_DIR / "databases" / "bls_qcew_industry.db"


def get_existing_years() -> set:
    """Queries SQLite layer to find all unique calendar years currently logged."""
    if not QCEW_DB_PATH.exists():
        return set()

    with sqlite3.connect(QCEW_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT year FROM qcew_annual_industry_records;")
        # Returns a quick hashing set for O(1) membership lookups in RAM
        return {int(row[0]) for row in cursor.fetchall() if row[0] is not None}


def process_local_folder_ingestion(folder_path: Path, target_year: int):
    """
    Reads all CSV data assets within the manually dropped year folder,
    normalizes the structures in your 64GB RAM, and writes to SQLite.
    """
    csv_files = sorted(list(folder_path.glob("*.csv")))
    if not csv_files:
        print(f" -> [SKIP] No CSV files found inside folder: {folder_path.name}")
        return

    print(f" -> [PROCESS] Loading {len(csv_files):,} county records into memory...")
    year_buffers = []

    for file_path in csv_files:
        try:
            df_county = pd.read_csv(file_path, low_memory=False)
            year_buffers.append(df_county)
        except Exception as e:
            print(f"    -> [WARN] Read failure on {file_path.name}: {str(e)}")

    if not year_buffers:
        return

    # High-RAM Vectorized Concat: Flatten all counties into memory instantly
    combined_df = pd.concat(year_buffers, ignore_index=True)
    combined_df.columns = [
        col.lower().strip().replace('"', "") for col in combined_df.columns
    ]

    rename_map = {
        "area_fips": "standardized_fips",
        "year": "year",
        "industry_code": "naics_code",
        "own_code": "own_code",
        "annual_avg_estabs_count": "establishment_count",
        "total_annual_wages": "total_annual_wages",
        "avg_annual_pay": "average_annual_pay",
    }

    # Replicate the annual average employment figure across your monthly fields
    if "annual_avg_emplvl" in combined_df.columns:
        combined_df["month_1_employment"] = combined_df["annual_avg_emplvl"]
        combined_df["month_2_employment"] = combined_df["annual_avg_emplvl"]
        combined_df["month_3_employment"] = combined_df["annual_avg_emplvl"]
    else:
        combined_df["month_1_employment"] = 0
        combined_df["month_2_employment"] = 0
        combined_df["month_3_employment"] = 0

    combined_df = combined_df.rename(columns=rename_map)

    # --- VECTORIZED FILTER PASS ---
    combined_df["standardized_fips"] = (
        combined_df["standardized_fips"].astype(str).str.strip().str.zfill(5)
    )
    combined_df["own_code"] = combined_df["own_code"].astype(str).str.strip()

    filtered_df = combined_df[
        (combined_df["own_code"] == "5")
        & (combined_df["standardized_fips"].str.len() == 5)
        & (~combined_df["standardized_fips"].str.endswith("000"))
    ].copy()

    if filtered_df.empty:
        print(
            f" -> [SKIP] No matching private sector paths identified in {folder_path.name}"
        )
        return

    filtered_df["naics_code"] = (
        filtered_df["naics_code"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    for col in [
        "year",
        "establishment_count",
        "month_1_employment",
        "month_2_employment",
        "month_3_employment",
    ]:
        filtered_df[col] = (
            pd.to_numeric(filtered_df[col], errors="coerce").fillna(0).astype(int)
        )

    ordered_df = filtered_df[
        [
            "standardized_fips",
            "year",
            "naics_code",
            "own_code",
            "establishment_count",
            "month_1_employment",
            "month_2_employment",
            "month_3_employment",
            "total_annual_wages",
            "average_annual_pay",
        ]
    ]

    # Write the entire year of processed rows to disk in a single transaction block
    print(
        f" -> [SQL] Committing {len(ordered_df):,} private county records to database..."
    )
    with sqlite3.connect(QCEW_DB_PATH) as conn:
        conn.execute("PRAGMA synchronous = OFF;")
        ordered_df.to_sql(
            "qcew_annual_industry_records", conn, if_exists="append", index=False
        )
    print(f" -> [SUCCESS] Year {target_year} successfully committed to database.")


def main():
    print("=" * 60)
    print("         QCEW DIRECTORY DISCOVERY & INCREMENTAL UPDATER")
    print("=" * 60)

    if not QCEW_TARGET_DIR.exists():
        print(f"[ABORT] Target data directory missing: {QCEW_TARGET_DIR.resolve()}")
        return

    # Step 1: Scan current database states
    existing_years = get_existing_years()
    print(
        f"[DATABASE] Unique calendar years currently indexed: {sorted(list(existing_years))}"
    )

    # Step 2: Scan for manually dropped folders matching 'YYYY.annual.by_area'
    discovered_folders = list(QCEW_TARGET_DIR.glob("*.annual.by_area"))
    print(
        f"[DIRECTORY] Discovered {len(discovered_folders)} target year folders on disk."
    )

    update_count = 0

    # Step 3: Check and process only missing years
    for folder_path in sorted(discovered_folders):
        year_digits = re.findall(r"\d{4}", folder_path.name)
        if not year_digits:
            continue
        folder_year = int(year_digits[0])

        print(f"\nEvaluating folder: {folder_path.name}")
        if folder_year in existing_years:
            print(
                f" -> [SKIP] Year {folder_year} data is already completely indexed in warehouse."
            )
        else:
            print(
                f" -> [NEW DATA] Year {folder_year} not found in database. Ingesting layer..."
            )
            process_local_folder_ingestion(folder_path, folder_year)
            update_count += 1

    print(
        f"\n[COMPLETE] Update sequence finished. Successfully processed {update_count} new annual blocks."
    )


if __name__ == "__main__":
    main()

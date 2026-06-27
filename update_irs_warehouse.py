import sqlite3
import csv
from pathlib import Path

# ====================================================================
# PATH CALCULATIONS
# ====================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
DB_PATH = (
    PROJECT_ROOT / "databases" / "irs_county_soi.db"
)  # Pointing to active database
IRS_RAW_DIR = PROJECT_ROOT / "raw_datasets" / "irs"


class IrsVintageUpdater:
    def __init__(self, db_path: Path, raw_dir: Path):
        self.db_path = str(db_path)
        self.raw_dir = raw_dir

    def append_vintage(self, file_name: str, calendar_year: int):
        """Streams a raw IRS 'incyall' CSV file directly into county_economics."""
        file_path = self.raw_dir / file_name
        if not file_path.exists():
            print(f"[SKIP] Raw source file missing at: {file_path.name}")
            return

        print(f"====================================================================")
        print(f"[INGEST] Processing Tax Year {calendar_year} | File: {file_path.name}")
        print(f"====================================================================")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Step 1: Guarantee idempotency by clearing existing rows for this vintage year
        cursor.execute(
            "DELETE FROM county_economics WHERE calendar_year = ?;", (calendar_year,)
        )

        insert_payload = []
        records_read = 0

        # Step 2: Stream raw CSV records
        with open(file_path, mode="r", encoding="latin-1") as f:
            reader = csv.DictReader(f)

            # Standardize raw headers to eliminate whitespace or case variance
            headers_map = {col.upper().strip(): col for col in reader.fieldnames}

            # Dynamically resolve common IRS SOI row variable headers
            state_key = headers_map.get("STATEFIPS") or headers_map.get("STATE")
            county_key = headers_map.get("COUNTYFIPS") or headers_map.get("COUNTY")
            name_key = headers_map.get("COUNTYNAME") or headers_map.get("NAME")
            returns_key = headers_map.get("N1") or headers_map.get("TOTAL_RETURNS")
            exempt_key = headers_map.get("N2") or headers_map.get("TOTAL_EXEMPTIONS")
            agi_key = headers_map.get("A00100") or headers_map.get(
                "ADJUSTED_GROSS_INCOME"
            )
            wages_key = headers_map.get("A00200") or headers_map.get(
                "WAGES_AND_SALARIES"
            )
            div_key = headers_map.get("A00600") or headers_map.get("DIVIDENDS_RECEIVED")
            int_key = headers_map.get("A00300") or headers_map.get("INTEREST_RECEIVED")

            # =================================================================
            # BULLETPROOF STRING NUMERIC PARSERS (THE FIX)
            # Strips commas, accounting brackets, and text spaces before casting
            # =================================================================
            def safe_int(val):
                if pd.isna(val) or str(val).strip() == "":
                    return 0
                # Scrub internal formatting metrics to isolate raw numeric string digits
                cleaned = (
                    str(val).replace(",", "").replace('"', "").replace("'", "").strip()
                )
                if cleaned.startswith("(") and cleaned.endswith(")"):
                    cleaned = "-" + cleaned[1:-1]
                try:
                    return int(float(cleaned))
                except ValueError:
                    return 0

            def safe_float(val):
                if pd.isna(val) or str(val).strip() == "":
                    return 0.0
                cleaned = (
                    str(val).replace(",", "").replace('"', "").replace("'", "").strip()
                )
                if cleaned.startswith("(") and cleaned.endswith(")"):
                    cleaned = "-" + cleaned[1:-1]
                try:
                    return float(cleaned)
                except ValueError:
                    return 0.0

            for row in reader:
                records_read += 1

                # Sift out total state summary records (County code '000') to isolate counties
                raw_co_code = row.get(county_key, "").strip()
                if raw_co_code in ("000", "0", ""):
                    continue

                raw_st_code = row.get(state_key, "").strip().zfill(2)
                formatted_fips = f"{raw_st_code}{raw_co_code.zfill(3)}"

                # Skip national placeholders
                if formatted_fips in ("00000", "99999"):
                    continue

                county_name = row.get(name_key, "").strip()

                total_returns = safe_int(row.get(returns_key))
                total_exemptions = safe_int(row.get(exempt_key))
                agi = safe_float(row.get(agi_key))
                wages = safe_float(row.get(wages_key))
                dividends = safe_float(row.get(div_key))
                interest = safe_float(row.get(int_key))

                insert_payload.append(
                    (
                        formatted_fips,
                        calendar_year,
                        county_name,
                        total_returns,
                        total_exemptions,
                        agi,
                        wages,
                        dividends,
                        interest,
                    )
                )

        # Step 3: Transaction Execution Block
        if insert_payload:
            cursor.executemany(
                """
                INSERT INTO county_economics (
                    county_fips,
                    calendar_year,
                    county_name,
                    total_returns,
                    total_exemptions,
                    adjusted_gross_income,
                    wages_and_salaries,
                    dividends_received,
                    interest_received
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                insert_payload,
            )
            conn.commit()
            print(f"SUCCESS: Read {records_read:,} total file lines.")
            print(f" Committed {len(insert_payload):,} clean county entries to disk.")
        else:
            print("⚠️ Ingestion halted: No valid county records extracted.")

        conn.close()


if __name__ == "__main__":
    import pandas as pd  # Added hook dependency for pd.isna safety checks

    updater = IrsVintageUpdater(DB_PATH, IRS_RAW_DIR)

    # add years to update filenames and year integer here
    updater.append_vintage("21incyallnoagi.csv", 2021)
    updater.append_vintage("22incyallnoagi.csv", 2022)
    print("\n[COMPLETE] Your independent IRS database is fully up to date.")

import sqlite3
import pandas as pd
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


# 1. Establish path frameworks down to your local directory setup
census_naics_dir = ROOT_DIR / "raw_datasets" / "census" / "naics"
db_path = ROOT_DIR / "databases" / "spatial_crosswalk.db"


if not db_path.exists():
    raise FileNotFoundError(f"Core spatial database absent at: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Clear out previous records to ensure a fresh, un-duplicated slate
print("Clearing values from dim_naics_crosswalk to reset data fields...")
cursor.execute("DELETE FROM dim_naics_crosswalk;")
conn.commit()


def ingest_by_column_position(
    filename, source_yr, target_yr, src_idx, tgt_idx, mapping_type, skip_rows_count
):
    """
    Locates local files, uses index coordinates (0, 1, 2) instead of text strings
    to isolate codes, strips formatting, and appends straight to SQLite.
    """
    file_path = census_naics_dir / filename
    if not file_path.exists():
        print(f"⚠️ Skipping missing local target: {filename}")
        return

    print(f"Processing structural map: {filename}...")

    # Read spreadsheet using your verified header offset row index positions
    df_raw = pd.read_excel(file_path, header=skip_rows_count)

    df_crosswalk = pd.DataFrame()

    # Extract codes using iloc positions to completely avoid string header mismatches
    df_crosswalk["source_naics"] = (
        df_raw.iloc[:, src_idx].astype(str).str.split(".").str[0].str.strip()
    )
    df_crosswalk["target_naics"] = (
        df_raw.iloc[:, tgt_idx].astype(str).str.split(".").str[0].str.strip()
    )

    df_crosswalk["source_year"] = int(source_yr)
    df_crosswalk["target_year"] = int(target_yr)
    df_crosswalk["mapping_type"] = mapping_type

    # Clean duplicates and empty entries
    df_crosswalk = df_crosswalk.dropna(subset=["source_naics", "target_naics"])

    # Enforce strict digit-only filtering to eliminate introductory text lines or footers
    digit_mask = (
        df_crosswalk["source_naics"].str.isdigit()
        & df_crosswalk["target_naics"].str.isdigit()
    )
    df_crosswalk = df_crosswalk[digit_mask]

    df_crosswalk = df_crosswalk.drop_duplicates(
        subset=["source_naics", "source_year", "target_year"]
    )

    # Append the clean matrix straight into your existing table architecture
    df_crosswalk.to_sql("dim_naics_crosswalk", conn, if_exists="append", index=False)
    print(f"  Successfully inserted {len(df_crosswalk)} distinct structural bridges.")


# =====================================================================
# 2. RUN EXTRACTION ENGINE USING VERIFIED COLUMN COORDINATES
# =====================================================================
try:
    # A. 2017 to 2022 Revision: Src is Column 0 (2017), Tgt is Column 2 (2022)
    ingest_by_column_position(
        filename="2017_to_2022_NAICS.xlsx",
        source_yr=2017,
        target_yr=2022,
        src_idx=0,
        tgt_idx=2,
        mapping_type="NAICS_REVISION",
        skip_rows_count=1,
    )

    # B. 2012 to 2017 Revision: Src is Column 0 (2012), Tgt is Column 2 (2017)
    ingest_by_column_position(
        filename="2012_to_2017_NAICS.xlsx",
        source_yr=2012,
        target_yr=2017,
        src_idx=0,
        tgt_idx=2,
        mapping_type="NAICS_REVISION",
        skip_rows_count=1,
    )

    # C. 2007 to 2012 Revision: Src is Column 0 (2007), Tgt is Column 2 (2012)
    ingest_by_column_position(
        filename="2007_to_2012_NAICS.xls",
        source_yr=2007,
        target_yr=2012,
        src_idx=0,
        tgt_idx=2,
        mapping_type="NAICS_REVISION",
        skip_rows_count=1,
    )

    # D. 2002 to 2007 Revision: Src is Column 0 (2002), Tgt is Column 2 (2007)
    ingest_by_column_position(
        filename="2002_to_2007_NAICS.xls",
        source_yr=2002,
        target_yr=2007,
        src_idx=0,
        tgt_idx=2,
        mapping_type="NAICS_REVISION",
        skip_rows_count=1,
    )

    # E. 1997 NAICS to 1987 SIC Legacy Mapping: Src is Column 3 (SIC), Tgt is Column 0 (1997 NAICS)
    # Based on your zero-skip preview: '1997 NAICS' is index 0, 'SIC' is index 3
    ingest_by_column_position(
        filename="1997_NAICS_to_1987_SIC.xls",
        source_yr=1987,
        target_yr=1997,
        src_idx=3,
        tgt_idx=0,
        mapping_type="SIC_TO_NAICS",
        skip_rows_count=0,
    )

    print("\n=========================================================================")
    print("      SUCCESS: YOUR NAICS CROSSWALK ENGINE IS FULLY PROVISIONED          ")
    print("=========================================================================")

    # Output absolute structural row counts now present in database table
    cursor.execute("SELECT COUNT(*) FROM dim_naics_crosswalk;")
    print(
        f"Total compiled historical bridging rows now in table: {cursor.fetchone()[0]}"
    )

except Exception as e:
    print(f"\n❌ Ingestion Halted Due to Extraction Error: {str(e)}")

finally:
    conn.close()

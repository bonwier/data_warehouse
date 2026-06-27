# build_laus_warehouse.py

import sqlite3
from pathlib import Path
import pandas as pd


def init_bls_database(db_path: Path) -> sqlite3.Connection:
    """Initializes the dedicated macro database with optimized storage engines and explicit composite indices."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable extreme write-performance flags for large in-memory bursts
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=OFF;")
    cursor.execute(
        "PRAGMA cache_size=-2000000;"
    )  # Allocates ~2GB of RAM for engine cache

    # 1. Establish core clustered index table layout
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS laus_monthly_records (
            series_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            period TEXT NOT NULL,
            value REAL NOT NULL,
            footnote_codes TEXT,
            state_fips TEXT NOT NULL,
            county_fips TEXT NOT NULL,
            measure_code TEXT NOT NULL,
            PRIMARY KEY (series_id, year, period)
        ) WITHOUT ROWID;
    """)

    # 2. FIXED: Composite Index includes measure_code and aligns with the query layout
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_laus_geo_structural_friction 
        ON laus_monthly_records (state_fips, county_fips, measure_code, year, value);
    """)

    conn.commit()
    return conn


def parse_and_load_bls_in_memory(file_path: Path, conn: sqlite3.Connection):
    """Loads and processes the complete BLS dataset entirely in RAM via vector operations."""
    if not file_path.exists():
        raise FileNotFoundError(f"Target BLS dataset missing at: {file_path.resolve()}")

    print(f"[*] Loading complete dataset into RAM: {file_path}")

    # Ingest entire file into memory instantly using space-delimited parsing
    df = pd.read_csv(
        file_path,
        sep=r"\s+",
        dtype={
            "series_id": str,
            "year": int,
            "period": str,
            "value": str,
            "footnote_codes": str,
        },
    )

    print(f"[*] Vector cleaning {len(df):,} raw records...")
    df["series_id"] = df["series_id"].str.strip()
    df["period"] = df["period"].str.strip()
    df["value"] = df["value"].str.strip()

    # Drop missing/uncalculated fields
    df = df[df["value"] != "-"].copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])

    print("[*] Slicing 20-character Series tokens via vectorized string arrays...")
    s_id_series = df["series_id"].str

    # Vectorized fast string extractions
    # FIXED: Re-aligned string slices to capture pristine census tokens from the 20-char Series ID
    df["state_fips"] = s_id_series.slice(5, 7)  # Extracts '01'
    df["county_fips"] = s_id_series.slice(7, 10)  # Extracts '001'
    df["measure_code"] = s_id_series.slice(18, 20)  # Extracts '03'

    # Handle optional footnotes uniformly
    if "footnote_codes" in df.columns:
        df["footnote_codes"] = df["footnote_codes"].fillna("").str.strip()
    else:
        df["footnote_codes"] = ""

    # Reorder structure to mirror the schema exactly
    df = df[
        [
            "series_id",
            "year",
            "period",
            "value",
            "footnote_codes",
            "state_fips",
            "county_fips",
            "measure_code",
        ]
    ]

    print(f"[*] Executing direct C-layer database transfer of {len(df):,} records...")

    # Extract raw tuple array to feed direct SQLite executemany
    records = list(df.itertuples(index=False, name=None))

    cursor = conn.cursor()
    # Wrap the entire batch inside a single atomic commit block
    cursor.execute("BEGIN TRANSACTION;")

    # Native executemany completely bypasses SQL variable/parameter length constraints
    cursor.executemany(
        """
        INSERT OR REPLACE INTO laus_monthly_records (
            series_id, year, period, value, footnote_codes, state_fips, county_fips, measure_code
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """,
        records,
    )

    conn.commit()
    print(f"[+] Successfully database-committed {len(df):,} unique macro rows.")


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent

    DB_TARGET = BASE_DIR / "databases" / "bls_laus_macro.db"
    DATA_SRC = BASE_DIR / "raw_datasets" / "bls" / "la.data.64.County"

    connection = init_bls_database(DB_TARGET)
    try:
        parse_and_load_bls_in_memory(DATA_SRC, connection)
    finally:
        connection.close()

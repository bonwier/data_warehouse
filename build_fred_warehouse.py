import sqlite3
import os
import datetime
from pathlib import Path
import pandas as pd
import pyfredapi as pf


def init_fred_database(db_path: Path) -> sqlite3.Connection:
    """
    Initializes the portable national macro indicators database on disk with an
    index-optimized clustered table structure.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=OFF;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fred_macro_indicators (
            series_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            value REAL NOT NULL,
            PRIMARY KEY (series_id, year, month)
        ) WITHOUT ROWID;
    """)
    conn.commit()
    return conn


def run_national_fred_refresh():
    """
    Extracts high-utility national shock anchors and 50-state Coincident Index
    momentum layers from FRED. Secures authorization via the root .env token.
    """
    root_dir = Path(__file__).resolve().parent
    db_target = root_dir / "databases" / "fred_macro_indicators.db"
    env_path = root_dir / ".env"

    if not env_path.exists():
        print(f"❌ Aborting. Environmental file missing at: {env_path}")
        return

    print(f"📖 Seeding credentials from root .env environment configuration...")
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith("FRED_API_KEY="):
                key_token = line.strip().split("=")[1].strip()
                os.environ["FRED_API_KEY"] = key_token

    if "FRED_API_KEY" not in os.environ or not os.environ["FRED_API_KEY"]:
        print(
            "❌ Authorization Failure. 'FRED_API_KEY' token is missing inside your .env file."
        )
        return

    # Spin up the storage engine
    conn = init_fred_database(db_target)

    # 1. Establish core national macroeconomic anchors
    national_targets = ["T10Y2Y", "UMCSENT"]

    # 2. Build the state-level targets for all 50 sovereign jurisdictions
    state_postal_codes = [
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
    ]
    state_targets = [f"{state}PHCI" for state in state_postal_codes]

    # Combine both lists to populate the database sequentially in one transaction loop
    all_targets = national_targets + state_targets

    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION;")

        for series in all_targets:
            print(f"[*] API Harvesting: Pulling series via pyfredapi: {series}")

            try:
                # Retrieve the series directly into a clean pandas DataFrame natively
                df = pf.get_series(series_id=series)
                if df is None or df.empty:
                    print(
                        f"⚠️ Warning: Received empty dataset for series {series}. Skipping."
                    )
                    continue

                df = df.dropna()

                # Formulate clear temporal parsing fields
                df["date"] = pd.to_datetime(df["date"])

                insert_payload = [
                    (
                        series.upper(),
                        int(row["date"].year),
                        int(row["date"].month),
                        float(row["value"]),
                    )
                    for _, row in df.iterrows()
                ]

                cursor.executemany(
                    "INSERT OR REPLACE INTO fred_macro_indicators VALUES (?,?,?,?);",
                    insert_payload,
                )
            except Exception as target_error:
                # Capture individual data feed issues without breaking the whole process
                print(f"❌ Failed to process series {series}: {str(target_error)}")
                continue

        conn.commit()
        print(
            f"✅ Refresh Complete! National & State macro indicators written cleanly to disk at:\n 👉 {db_target}"
        )

    except Exception as e:
        conn.execute("ROLLBACK;")
        print(
            f"❌ Pipeline Interrupted. Transaction rolled back safely. Issue: {str(e)}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    run_national_fred_refresh()

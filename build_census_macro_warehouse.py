import sqlite3
import os
import time
from pathlib import Path
import pandas as pd
import numpy as np


def load_census_api_key() -> str:
    """Extracts the secure CENSUS_API_KEY string directly from your root .env file."""
    root_dir = Path(__file__).resolve().parent
    env_path = root_dir / ".env"

    if not env_path.exists():
        raise FileNotFoundError(f"❌ Missing environmental target at: {env_path}")

    with open(env_path, "r") as f:
        for line in f:
            if line.startswith("CENSUS_API_KEY="):
                return line.strip().split("=")[1].strip()

    raise KeyError(
        "❌ API Key Token absent. 'CENSUS_API_KEY' variable missing inside .env."
    )


def init_census_database(db_path: Path) -> sqlite3.Connection:
    """Initializes the dedicated national state macro warehouse database on disk."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=OFF;")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS census_state_indicators (
            state_fips TEXT NOT NULL,
            year INTEGER NOT NULL,
            quarter INTEGER NOT NULL,
            separation_rate REAL NOT NULL,
            net_job_flow_count INTEGER NOT NULL,
            PRIMARY KEY (state_fips, year, quarter)
        ) WITHOUT ROWID;
    """)
    conn.commit()
    return conn


def harvest_census_qwi_for_state(state_fips: str, api_key: str) -> pd.DataFrame:
    """
    Ingests QWI flow indicators using the verified FrmJbC variable,
    wrapped explicitly inside a clean HTTPS string literal layout.
    """
    # FIXED: Replaced invalid variable name with the verified FrmJbC token
    target_url = (
        f"https://api.census.gov/data/timeseries/qwi/sa"
        f"?get=Sep,Emp,FrmJbC"
        f"&for=state:{state_fips}"
        f"&time=from+2010-Q1+to+2024-Q4"
        f"&ownercode=A05"
        f"&industry=00"
        f"&sex=0"
        f"&agegrp=A00"
        f"&seasonadj=U"
        f"&key={api_key}"
    )

    try:
        # Stream the JSON response matrix directly into Pandas via its C-engine
        raw_data = pd.read_json(target_url)

        # Formulate clean data frame column headers out of row zero
        headers = raw_data.iloc[0].tolist()
        df = pd.DataFrame(raw_data.values[1:], columns=headers)

        # Parse the dynamic 'time' response column string ('YYYY-Q#') into distinct integers
        if "time" in df.columns and "year" not in df.columns:
            df["year"] = df["time"].str.split("-").str[0]
            df["quarter"] = df["time"].str.split("-").str[1].str.replace("Q", "")

        # Standardize numeric casting boundaries cleanly
        for col in ["Sep", "Emp", "FrmJbC", "year", "quarter"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["Sep", "Emp", "FrmJbC", "year", "quarter"])

        # Calculate population-agnostic state industry turnover
        df["separation_rate"] = np.where(df["Emp"] > 0, df["Sep"] / df["Emp"], 0.0)

        df["state_fips"] = df["state"].astype(str).str.strip().str.zfill(2)
        return df[["state_fips", "year", "quarter", "separation_rate", "FrmJbC"]]

    except Exception as e:
        print(
            f"  ⚠️ Warning: Query execution failed for State FIPS {state_fips}: {str(e)}"
        )
        return pd.DataFrame()


def execute_warehouse_build():
    """Loops through all states sequentially to construct the data warehouse layer."""
    root_dir = Path(__file__).resolve().parent
    db_target = root_dir / "databases" / "census_state_macro.db"

    api_key = load_census_api_key()
    conn = init_census_database(db_target)

    state_fips_list = [
        "01",
        "02",
        "04",
        "05",
        "06",
        "08",
        "09",
        "10",
        "12",
        "13",
        "15",
        "16",
        "17",
        "18",
        "19",
        "20",
        "21",
        "22",
        "23",
        "24",
        "25",
        "26",
        "27",
        "28",
        "29",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
        "36",
        "37",
        "38",
        "39",
        "40",
        "41",
        "42",
        "44",
        "45",
        "46",
        "47",
        "48",
        "49",
        "50",
        "51",
        "53",
        "54",
        "55",
        "56",
    ]

    print(
        f"🚀 Initiating script-literal API ingestion across {len(state_fips_list)} states..."
    )

    for fips in state_fips_list:
        df_state = harvest_census_qwi_for_state(fips, api_key)
        if df_state.empty:
            continue

        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION;")

            # Map column tokens perfectly to your database schema requirements
            insert_payload = [
                (
                    row["state_fips"],
                    int(row["year"]),
                    int(row["quarter"]),
                    float(row["separation_rate"]),
                    int(row["FrmJbC"]),
                )
                for _, row in df_state.iterrows()
            ]

            cursor.executemany(
                "INSERT OR REPLACE INTO census_state_indicators VALUES (?,?,?,?,?);",
                insert_payload,
            )
            conn.commit()
            print(
                f"  • State FIPS {fips} synchronized successfully ({len(insert_payload)} quarters added)."
            )

            # Politeness delay to ensure gateway safety metrics are respected
            time.sleep(0.2)

        except Exception as e:
            try:
                conn.execute("ROLLBACK;")
            except sqlite3.OperationalError:
                pass
            print(f"  ❌ Failed to commit data block for FIPS {fips}: {str(e)}")
            continue

    conn.close()
    print(
        f"✅ National State Macro Warehouse Complete! Generated file at:\n    👉 {db_target}"
    )


if __name__ == "__main__":
    execute_warehouse_build()

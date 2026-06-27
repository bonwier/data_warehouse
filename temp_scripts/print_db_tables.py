import sqlite3
from pathlib import Path

from pathlib import Path

# Establish deterministic runtime base tracking relative to this script file
DATABASES = [
    "sba_7a_analysis.db",
    "bls_laus_macro.db",
    "bls_qcew_industry.db",
    "irs_county_soi.db",
    "spatial_crosswalk.db",
]


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Centralized path anchors
DATABASE_DIR = PROJECT_ROOT / "databases"


def print_table_details(db):
    # Connect to the database
    db_path = DATABASE_DIR / db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query to fetch the names of all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    if not tables:
        print(f"No tables found in '{db_path.name}'.")
        return

    print(f"Details for tables in {db_path.name}:\n")

    # Iterate through tables and fetch their schema (SQL used to create them)
    for table_info in tables:
        table_name = table_info[0]

        cursor.execute(
            f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';"
        )
        schema = cursor.fetchone()[0]

        print(f"--- Table: {table_name} ---")
        print(schema)
        print("-" * 40 + "\n")

    # Close the database connection
    conn.close()


if __name__ == "__main__":

    for db in DATABASES:
        print_table_details(db)

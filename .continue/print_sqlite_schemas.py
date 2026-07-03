import json
import sqlite3
from pathlib import Path

# =====================================================================
# 1. DETERMINISTIC RUNTIME BASE TRACKING
# =====================================================================
SCRIPT_DIR = (
    Path(__file__).resolve().parent if "__file__" in locals() else Path(".").resolve()
)
PROJECT_ROOT = SCRIPT_DIR
while PROJECT_ROOT.name != "data_warehouse" and PROJECT_ROOT.parent != PROJECT_ROOT:
    PROJECT_ROOT = PROJECT_ROOT.parent

# Centralized path anchors
DATABASE_DIR = PROJECT_ROOT / "databases"
TRANSITORY_DIR = DATABASE_DIR / "transitory"

# Dual Output Files inside your Continue configuration folder
MASTER_SCHEMA_FILE = PROJECT_ROOT / ".continue" / "db_schema.txt"
SLIM_SCHEMA_FILE = PROJECT_ROOT / ".continue" / "db_schema_slim.txt"


def generate_schema_report(db_path: Path, output_file):
    """Inspects an active SQLite database and writes parsed layouts to file."""
    if not db_path.exists():
        return

    relative_display_name = db_path.relative_to(PROJECT_ROOT)
    print(f"--- FILE: {relative_display_name} ---", file=output_file)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = cursor.fetchall()

        if not tables:
            print("  (No user tables discovered inside database)\n", file=output_file)
            return

        for table_name in sorted([t[0] for t in tables]):
            cursor.execute(
                f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';"
            )
            sql_res = cursor.fetchone()
            is_without_rowid = (
                "WITHOUT ROWID" in sql_res[0].upper()
                if sql_res and sql_res[0]
                else False
            )
            rowid_flag = " (WITHOUT ROWID)" if is_without_rowid else ""

            print(f"Table: {table_name}{rowid_flag}", file=output_file)

            cursor.execute(f"PRAGMA table_info('{table_name}');")
            columns = cursor.fetchall()

            for col in columns:
                col_name = col[1]
                col_type = col[2] if col[2] else "TEXT"
                is_pk = " (PK)" if col[5] > 0 else ""
                print(f"  - {col_name} {col_type}{is_pk}", file=output_file)

            print("", file=output_file)

    except Exception as e:
        print(f"  ❌ Error parsing database: {str(e)}\n", file=output_file)
    finally:
        conn.close()


if __name__ == "__main__":
    print("🧠 Starting automated dual schema scan...")
    MASTER_SCHEMA_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 1. Discover all databases
    all_dbs = list(DATABASE_DIR.glob("*.db")) + list(DATABASE_DIR.glob("*.sqlite"))
    if TRANSITORY_DIR.exists():
        all_dbs += list(TRANSITORY_DIR.glob("*.db")) + list(
            TRANSITORY_DIR.glob("*.sqlite")
        )

    # 2. Separate into Core (Slim) vs Macro (Extended) collections
    slim_targets = ["spatial_crosswalk.db", "sba_7a_analysis.db", "irs_county_soi.db"]
    slim_dbs = [db for db in all_dbs if db.name in slim_targets]

    # 3. WRITE MASTER REPORT (For Gemini 3 Flash)
    with open(MASTER_SCHEMA_FILE, "w", encoding="utf-8") as f_master:
        print(
            "========================================================================",
            file=f_master,
        )
        print("MASTER SYSTEM BLUEPRINT CATALOG (GEMINI COMPREHENSIVE)", file=f_master)
        print(
            "========================================================================\n",
            file=f_master,
        )
        for db in sorted(all_dbs):
            generate_schema_report(db, output_file=f_master)

    # 4. WRITE SLIM REPORT (For Local Qwen 7B CPU Acceleration)
    with open(SLIM_SCHEMA_FILE, "w", encoding="utf-8") as f_slim:
        print(
            "========================================================================",
            file=f_slim,
        )
        print("SLIM DATA CREDIT CATALOG (LOCAL MODEL ACCELERATED)", file=f_slim)
        print(
            "========================================================================\n",
            file=f_slim,
        )
        for db in sorted(slim_dbs):
            generate_schema_report(db, output_file=f_slim)

    print(f"✅ Master Gemini database schema compiled to: {MASTER_SCHEMA_FILE}")
    print(f"🚀 Slim Qwen local database schema compiled to: {SLIM_SCHEMA_FILE}")

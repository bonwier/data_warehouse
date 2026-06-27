import sqlite3
import re
import json
from pathlib import Path

# ==================================================================== #
# PATH DISCOVERY VIA PATHLIB                                           #
# ==================================================================== #
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATABASES_DIR = PROJECT_ROOT / "databases"
RAW_DATA_DIR = PROJECT_ROOT / "raw_datasets"

# Dynamic targets synchronized to your exact repository state
CROSSWALK_DB = DATABASES_DIR / "spatial_crosswalk.db"
IMMUTABLE_IRS_DB = DATABASES_DIR / "irs_county_soi.db"
LOCAL_CENSUS_FILE = RAW_DATA_DIR / "census" / "national_county2020.txt"
BLS_AREA_FILE = RAW_DATA_DIR / "bls" / "la.area"
BLS_DATA_FILE = RAW_DATA_DIR / "bls" / "la.data.64.County"
COUNTYCROSSWALK_JSON = RAW_DATA_DIR / "geo_to_fips_map.json"


class ConsolidatedCrosswalkEngine:
    def __init__(self):
        # Bound array tracking every major structural boundary change from 1989-2020
        self.legacy_mutations = [
            {
                "fips": "51780",
                "name": "South Boston City",
                "state": "VA",
                "start": 1989,
                "end": 1995,
                "successor": "51083",
            },
            {
                "fips": "12025",
                "name": "Dade County",
                "state": "FL",
                "start": 1989,
                "end": 1997,
                "successor": "12086",
            },
            {
                "fips": "12086",
                "name": "Miami-Dade County",
                "state": "FL",
                "start": 1997,
                "end": 9999,
                "successor": None,
            },
            {
                "fips": "08014",
                "name": "Broomfield County",
                "state": "CO",
                "start": 2001,
                "end": 9999,
                "successor": None,
            },
            {
                "fips": "02201",
                "name": "Prince of Wales-Outer Ketchikan",
                "state": "AK",
                "start": 1989,
                "end": 2008,
                "successor": "02198",
            },
            {
                "fips": "02232",
                "name": "Skagway-Hoonah-Angoon",
                "state": "AK",
                "start": 1989,
                "end": 2007,
                "successor": "02105",
            },
            {
                "fips": "02261",
                "name": "Valdez-Cordova Census Area",
                "state": "AK",
                "start": 1989,
                "end": 2019,
                "successor": "02063",
            },
            {
                "fips": "02270",
                "name": "Wade Hampton Census Area",
                "state": "AK",
                "start": 1989,
                "end": 2015,
                "successor": "02158",
            },
            {
                "fips": "02280",
                "name": "Wrangell-Petersburg Census Area",
                "state": "AK",
                "start": 1989,
                "end": 2008,
                "successor": "02195",
            },
            {
                "fips": "46113",
                "name": "Shannon County",
                "state": "SD",
                "start": 1989,
                "end": 2015,
                "successor": "46102",
            },
            {
                "fips": "46102",
                "name": "Oglala Lakota County",
                "state": "SD",
                "start": 2015,
                "end": 9999,
                "successor": None,
            },
            {
                "fips": "02158",
                "name": "Kusilvak Census Area",
                "state": "AK",
                "start": 2015,
                "end": 9999,
                "successor": None,
            },
            {
                "fips": "02063",
                "name": "Chugach Census Area",
                "state": "AK",
                "start": 2019,
                "end": 9999,
                "successor": None,
            },
            {
                "fips": "02066",
                "name": "Copper River Census Area",
                "state": "AK",
                "start": 2019,
                "end": 9999,
                "successor": None,
            },
        ]
        # Explicit overrides to re-align custom BLS 70000 series metrics back to standard FIPS
        self.bls_70000_overrides = {
            "70001": "09001",
            "70003": "09003",
            "70005": "09005",
            "70007": "09007",
            "70009": "09009",
            "70011": "09011",
            "70013": "09013",
            "70015": "09015",
        }

    def init_schema(self):
        """Initializes tables using explicit integrity targets."""
        with sqlite3.connect(CROSSWALK_DB) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS dim_geography_fips (
                    standardized_fips TEXT PRIMARY KEY CHECK (length(standardized_fips) = 5),
                    county_name TEXT NOT NULL,
                    state_postal TEXT NOT NULL CHECK (length(state_postal) = 2),
                    date_created INTEGER NOT NULL,
                    date_retired INTEGER NOT NULL DEFAULT 9999,
                    successor_fips TEXT,
                    FOREIGN KEY (successor_fips) REFERENCES dim_geography_fips(standardized_fips)
                );

                CREATE TABLE IF NOT EXISTS map_source_to_fips (
                    source_agency TEXT NOT NULL,
                    source_code TEXT NOT NULL,
                    data_year INTEGER NOT NULL,
                    standardized_fips TEXT NOT NULL,
                    handling_rule TEXT NOT NULL DEFAULT 'DIRECT_MAP',
                    PRIMARY KEY (source_agency, source_code, data_year),
                    FOREIGN KEY (standardized_fips) REFERENCES dim_geography_fips(standardized_fips)
                );

                CREATE INDEX IF NOT EXISTS idx_crosswalk_speed ON map_source_to_fips (source_agency, source_code, data_year);

                CREATE TABLE IF NOT EXISTS map_county_text_to_fips (
                    lookup_key TEXT PRIMARY KEY,
                    standardized_fips TEXT NOT NULL,
                    FOREIGN KEY (standardized_fips) REFERENCES dim_geography_fips(standardized_fips)
                );

                CREATE INDEX IF NOT EXISTS idx_county_text ON map_county_text_to_fips(lookup_key);

                -- NEW: Longitudinal Industry Evolution Ledger for SBA 7a Risk Models
                CREATE TABLE IF NOT EXISTS dim_naics_crosswalk (
                    source_naics TEXT NOT NULL,
                    source_year INTEGER NOT NULL,
                    target_year INTEGER NOT NULL,
                    target_naics TEXT NOT NULL,
                    mapping_type TEXT NOT NULL CHECK (mapping_type IN ('SIC_TO_NAICS', 'NAICS_REVISION')),
                    PRIMARY KEY (source_naics, source_year, target_year)
                );

                CREATE INDEX IF NOT EXISTS idx_naics_evolution ON dim_naics_crosswalk(source_naics, source_year);
            """)
        print("[SCHEMA] Spatial crosswalk and industry evolution tables compiled.")

    def seed_master_ledger_from_local_census(self):
        """Parses the local pipe-delimited Census file to build foundational records."""
        if not LOCAL_CENSUS_FILE.exists():
            print(f"[FATAL] Local reference asset missing at: {LOCAL_CENSUS_FILE}")
            return
        records = []
        with open(LOCAL_CENSUS_FILE, mode="r", encoding="utf-8") as f:
            f.readline()
            for line in f:
                parts = line.strip().split("|")
                if len(parts) < 5:
                    continue
                state_postal = parts[0].strip()
                state_fips = parts[1].strip().zfill(2)
                county_fips = parts[2].strip().zfill(3)
                county_name = parts[4].strip()
                records.append(
                    (
                        f"{state_fips}{county_fips}",
                        county_name,
                        state_postal,
                        1989,
                        9999,
                        None,
                    )
                )

        with sqlite3.connect(CROSSWALK_DB) as conn:
            conn.executemany(
                """
                INSERT INTO dim_geography_fips (standardized_fips, county_name, state_postal, date_created, date_retired, successor_fips)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(standardized_fips) DO UPDATE SET county_name = excluded.county_name;
            """,
                records,
            )

            states = conn.execute(
                "SELECT DISTINCT state_postal, substr(standardized_fips, 1, 2) FROM dim_geography_fips"
            ).fetchall()
            fallbacks = [
                (
                    f"{st_fips}000",
                    f"{st_code} General Fallback Aggregate",
                    st_code,
                    1989,
                    9999,
                    None,
                )
                for st_code, st_fips in states
            ]
            conn.executemany(
                "INSERT INTO dim_geography_fips VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING;",
                fallbacks,
            )

            for m in self.legacy_mutations:
                conn.execute(
                    """
                    INSERT INTO dim_geography_fips (standardized_fips, county_name, state_postal, date_created, date_retired, successor_fips)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(standardized_fips) DO UPDATE SET date_retired = excluded.date_retired, successor_fips = excluded.successor_fips;
                """,
                    (
                        m["fips"],
                        m["name"],
                        m["state"],
                        m["start"],
                        m["end"],
                        m["successor"],
                    ),
                )
        print("[SEED] Baseline geographical anchors and lineages finalized.")

    def seed_industry_crosswalk(self):
        """
        Seeds structural industry conversions. Maps legacy 4-digit SIC codes (1991-1996 SBA loans)
        and handles structural Census NAICS revisions across major historical model epochs.
        """
        industry_payload = [
            # --- 1. HISTORICAL SIC-TO-NAICS SECTOR SEEDS (1991-1996 SBA Loans to 1997 NAICS Standards) ---
            (
                "5812",
                1991,
                1997,
                "722511",
                "SIC_TO_NAICS",
            ),  # Eating Places -> Full-Service Restaurants
            (
                "5411",
                1991,
                1997,
                "445110",
                "SIC_TO_NAICS",
            ),  # Grocery Stores -> Supermarkets/Grocery
            (
                "7532",
                1993,
                1997,
                "811121",
                "SIC_TO_NAICS",
            ),  # Top/Body Repair -> Automotive Body/Paint
            (
                "0782",
                1991,
                1997,
                "561730",
                "SIC_TO_NAICS",
            ),  # Lawn & Garden Services -> Landscaping Services
            # --- 2. TRANSITIONAL NAICS CENSUS REVISIONS (Tracking multi-decade structural drift) ---
            (
                "514110",
                2002,
                2007,
                "424410",
                "NAICS_REVISION",
            ),  # General Line Grocery Wholesale Shift
            (
                "443112",
                2007,
                2012,
                "443142",
                "NAICS_REVISION",
            ),  # Radio/TV/Electronics Stores -> Electronics Stores
            (
                "722110",
                2007,
                2012,
                "722511",
                "NAICS_REVISION",
            ),  # Full-Service Restaurants Standard Realignment
            (
                "722211",
                2007,
                2012,
                "722513",
                "NAICS_REVISION",
            ),  # Limited-Service Restaurants Revision
            (
                "452111",
                2017,
                2022,
                "455110",
                "NAICS_REVISION",
            ),  # Department Stores -> General Merchandise
            (
                "454110",
                2017,
                2022,
                "454110",
                "NAICS_REVISION",
            ),  # Electronic Shopping stays consistent
        ]

        with sqlite3.connect(CROSSWALK_DB) as conn:
            conn.executemany(
                """
                INSERT INTO dim_naics_crosswalk (source_naics, source_year, target_year, target_naics, mapping_type)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_naics, source_year, target_year) DO UPDATE SET
                    target_naics = excluded.target_naics,
                    mapping_type = excluded.mapping_type;
            """,
                industry_payload,
            )
        print(
            f"[SEED] Industry longitudinal crosswalk updated. {len(industry_payload)} core mappings indexed."
        )

    def ingest_repaired_irs_database(self):
        """Attaches irs_county_soi.db to compute historical timelines up to 2022."""
        if not IMMUTABLE_IRS_DB.exists():
            print(f"[SKIP] IRS source database missing at: {IMMUTABLE_IRS_DB.name}")
            return
        conn = sqlite3.connect(CROSSWALK_DB)
        cursor = conn.cursor()
        cursor.execute(f"ATTACH DATABASE '{IMMUTABLE_IRS_DB}' AS source_soi;")
        cursor.execute("""
            SELECT DISTINCT county_fips, calendar_year FROM source_soi.county_economics
            WHERE county_fips IS NOT NULL AND calendar_year IS NOT NULL;
        """)
        rows = cursor.fetchall()
        payload = []
        for raw_fips, year in rows:
            clean_fips = str(raw_fips).strip().zfill(5)
            if clean_fips in ("00000", "99999"):
                continue
            cursor.execute(
                "SELECT 1 FROM dim_geography_fips WHERE standardized_fips = ?;",
                (clean_fips,),
            )
            if cursor.fetchone():
                payload.append(
                    ("IRS_SOI", str(raw_fips), year, clean_fips, "DIRECT_MAP")
                )
            else:
                state_prefix = clean_fips[0:2]
                payload.append(
                    (
                        "IRS_SOI",
                        str(raw_fips),
                        year,
                        f"{state_prefix}000",
                        "STATE_FALLBACK",
                    )
                )

        cursor.executemany(
            """
            INSERT INTO map_source_to_fips (source_agency, source_code, data_year, standardized_fips, handling_rule)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING;
        """,
            payload,
        )
        conn.commit()
        cursor.execute("DETACH DATABASE source_soi;")
        conn.close()
        print(f"[INGEST] IRS Timeline sync complete. {len(payload)} records mapped.")

    def ingest_bls_flat_files(self):
        """Parses bulk BLS 20-character text strings and extracts 5-digit FIPS tokens directly."""
        if not BLS_DATA_FILE.exists():
            print(
                "[SKIP] Bulk BLS data file missing from raw_datasets/bls/. Skipping layer."
            )
            return
        print("[BLS] Processing bulk labor statistics records...")
        payload = []
        unique_tracker = set()
        with open(BLS_DATA_FILE, mode="r", encoding="utf-8") as f:
            f.readline()
            for line in f:
                parts = re.split(r"\s+", line.strip())
                if len(parts) < 2:
                    continue
                series_id = parts[0].strip()
                year = int(parts[1])

                if len(series_id) == 20 and series_id.startswith("LAUCN"):
                    extracted_fips = series_id[5:10]
                    rule = "DIRECT_MAP"
                    if extracted_fips in self.bls_70000_overrides:
                        extracted_fips = self.bls_70000_overrides[extracted_fips]
                        rule = "BLS_70000_OVERRIDE"

                    track_key = (series_id, year)
                    if track_key in unique_tracker:
                        continue
                    unique_tracker.add(track_key)
                    payload.append(("BLS_LAUS", series_id, year, extracted_fips, rule))

        with sqlite3.connect(CROSSWALK_DB) as conn:
            conn.executemany(
                """
                INSERT INTO map_source_to_fips (source_agency, source_code, data_year, standardized_fips, handling_rule)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING;
            """,
                payload,
            )
        print(f"[INGEST] BLS Timeline sync complete. {len(payload)} records mapped.")

    def seed_county_text_lookup_table(self):
        """Parses your large external JSON file and streams it directly into a permanent relational database index."""
        if not COUNTYCROSSWALK_JSON.exists():
            print(
                f"[ERROR] External JSON lookup file missing at: {COUNTYCROSSWALK_JSON}"
            )
            return
        print(f"[SEED] Ingesting large county-to-fips translation ledger from JSON...")
        with open(COUNTYCROSSWALK_JSON, mode="r", encoding="utf-8") as f:
            county_map_dict = json.load(f)
        payload = [
            (key.strip().upper(), str(fips).strip().zfill(5))
            for key, fips in county_map_dict.items()
        ]

        with sqlite3.connect(CROSSWALK_DB) as conn:
            conn.executemany(
                """
                INSERT INTO map_county_text_to_fips (lookup_key, standardized_fips)
                VALUES (?, ?)
                ON CONFLICT(lookup_key) DO UPDATE SET standardized_fips = excluded.standardized_fips;
            """,
                payload,
            )
        print(
            f"[SEED] County text lookup engine finalized. {len(payload):,} strings indexed."
        )


if __name__ == "__main__":
    engine = ConsolidatedCrosswalkEngine()
    engine.init_schema()
    engine.seed_master_ledger_from_local_census()
    engine.seed_industry_crosswalk()  # <--- Safely injected inline within sequence execution
    engine.ingest_repaired_irs_database()
    engine.ingest_bls_flat_files()
    engine.seed_county_text_lookup_table()
    print("\n[SUCCESS] spatial_crosswalk.db generation successfully completed.")

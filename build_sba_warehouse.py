"""
Location: build_sba_warehouse.py (Part 1 of 2)
Description: Streamlined warehouse script that constructs a project-neutral,
             two-tiered architecture: a complete raw history table and a
             pristine, un-censored survival cohort table for 2003-present.
"""

import sqlite3
import sys
import os
import logging
from pathlib import Path
import pandas as pd
import numpy as np

# 1. Logging Infrastructure Configuration for Audit Compliance
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("warehouse_rebuild_execution.log", mode="w"),
    ],
)
logger = logging.getLogger("Warehouse_Build_Engine")


def clean_currency_vectorized(series: pd.Series) -> pd.Series:
    """Vectorized currency cleaner handling strings, commas, symbols, and accounting parentheses."""
    s_str = series.fillna("0.0").astype(str)
    s_str = s_str.str.replace(r"[$\s,)]", "", regex=True)
    s_str = s_str.str.replace(r"\(", "-", regex=True)
    return pd.to_numeric(s_str, errors="coerce").fillna(0.0)


def main():
    # Dynamic Path Anchoring via pathlib
    ROOT_DIR = Path(__file__).resolve().parent
    DB_PATH = ROOT_DIR / "databases" / "sba_7a_analysis.db"
    SPATIAL_DB_PATH = ROOT_DIR / "databases" / "spatial_crosswalk.db"
    SBA_7A_DIR = ROOT_DIR / "raw_datasets" / "sba" / "7a"

    FOIA_FILES = [
        SBA_7A_DIR / "foia-7a-fy1991-fy1999-asof-260331.csv",
        SBA_7A_DIR / "foia-7a-fy2000-fy2009-asof-260331.csv",
        SBA_7A_DIR / "foia-7a-fy2010-fy2019-asof-260331.csv",
        SBA_7A_DIR / "foia-7a-fy2020-present-asof-260331.csv",
    ]

    MASTER_TABLE = "sba_7a_loans"
    COHORT_TABLE = "model_cohort_2003_present"

    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    # Lazy-load utilities now that path context is locked down
    from utils.geography_daemon import GeographyDaemon

    geo_daemon = GeographyDaemon()

    # -----------------------------------------------------------------
    # PHASE 1: BULK INGESTION AND FILE CONSOLIDATION
    # -----------------------------------------------------------------
    df_list = []
    logger.info("--- Unified SBA 7(a) Warehouse Engine Initiated ---")
    logger.info("Loading raw source files completely into RAM panel layers...")

    for file_path in FOIA_FILES:
        if file_path.exists():
            logger.info(f"Reading: {file_path.name}")
            df_list.append(pd.read_csv(file_path, low_memory=False))
        else:
            logger.error(f"CRITICAL ERROR: Source file missing: {file_path}")
            geo_daemon.close()
            return

    df = pd.concat(df_list, ignore_index=True)
    logger.info(f"Total raw administrative records compiled: {len(df):,}")

    # -----------------------------------------------------------------
    # PHASE 2: BASELINE STANDARDIZATION & STRUCTURAL CLEANING
    # -----------------------------------------------------------------
    logger.info(
        "Executing baseline column characterizations and financial conversions..."
    )
    df["jobssupported_clean"] = (
        pd.to_numeric(df["jobssupported"], errors="coerce").fillna(0).astype(int)
    )
    df["grossapproval_clean"] = clean_currency_vectorized(df["grossapproval"])
    df["approvalfy_clean"] = (
        pd.to_numeric(df["approvalfy"], errors="coerce").fillna(0).astype(int)
    )

    # Vectorize NAICS 2-digit high level tags
    df["naics2digit"] = (
        df["naicscode"]
        .fillna("")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str[:2]
    )
    df["naics2digit"] = np.where(
        df["naics2digit"].str.isdigit(), df["naics2digit"], "00"
    )

    # Track franchises and raw default stamps
    df["franchisecode_str"] = df["franchisecode"].fillna("").astype(str)
    df["isfranchise"] = np.where(
        (df["franchisecode_str"] != "")
        & (df["franchisecode_str"].str.lower() != "nan"),
        1,
        0,
    )

    df["chargeoffdate_str"] = df["chargeoffdate"].fillna("").astype(str)
    df["isdefaulted"] = np.where(
        (df["chargeoffdate_str"] != "")
        & (df["chargeoffdate_str"].str.lower() != "nan"),
        1,
        0,
    )
    df["goodwill_ratio"] = 1.0

    # -----------------------------------------------------------------
    # PHASE 3: ADMINISTRATIVE LIFECYCLE DEDUPLICATION
    # -----------------------------------------------------------------
    logger.info(
        "Resolving raw portfolio multi-disbursement transactions via administrative ranking..."
    )
    df["loanstatus_clean"] = (
        df["loanstatus"].fillna("").astype(str).str.strip().str.upper()
    )
    status_conditions = [
        df["loanstatus_clean"].str.contains("CHG|OFF|DEFAULT", na=False),
        df["loanstatus_clean"].str.contains("P I F|PAID", na=False),
        df["loanstatus_clean"].str.contains("CURR|COMMIT", na=False),
    ]
    status_choices = [3, 2, 1]
    df["lifecycle_priority"] = np.select(status_conditions, status_choices, default=0)

    df["fingerprint"] = (
        df["borrname"].fillna("").astype(str)
        + "_"
        + df["borrstreet"].fillna("").astype(str)
        + "_"
        + df["approvaldate"].fillna("").astype(str)
        + "_"
        + df["grossapproval"].fillna("").astype(str)
    )

    df = df.sort_values(
        by=["fingerprint", "lifecycle_priority", "isdefaulted"], ascending=True
    )
    df = df.drop_duplicates(subset=["fingerprint"], keep="last")
    logger.info(
        f"Deduplication complete. Retained {len(df):,} unique tracking transactions."
    )

    # -----------------------------------------------------------------
    # PHASE 4: PERSISTENCE MATRIX WRITING - TIER 1 ARCHIVE
    # -----------------------------------------------------------------
    logger.info(f"Opening persistence stream to SQLite layout: {DB_PATH}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")  # Maximize stream performance

    logger.info(
        f"Writing complete 100% raw history archive to table '{MASTER_TABLE}'..."
    )
    helper_cols = [
        "jobssupported_clean",
        "grossapproval_clean",
        "approvalfy_clean",
        "franchisecode_str",
        "chargeoffdate_str",
        "loanstatus_clean",
        "lifecycle_priority",
        "fingerprint",
    ]
    master_clean_df = df.drop(columns=helper_cols, errors="ignore")
    master_clean_df.to_sql(MASTER_TABLE, conn, if_exists="replace", index=False)

    # Continuation of main() execution loop from Part 1...

    # -----------------------------------------------------------------
    # PHASE 5: PERSISTENCE MATRIX WRITING - TIER 2 PRISTINE MODEL COHORT (2003+)
    # -----------------------------------------------------------------
    logger.info(
        f"Compiling neutral risk modeling core table '{COHORT_TABLE}' (Left-Censored at 2003)..."
    )
    df_cohort = df[df["approvalfy_clean"] >= 2003].copy()

    # 1. Operational Risk Gate: Drop Cancelled / Unfunded rows using your priority tiers
    df_cohort = df_cohort[df_cohort["lifecycle_priority"].isin([1, 2, 3])].copy()
    df_cohort = df_cohort[df_cohort["firstdisbursementdate"].notna()].copy()
    df_cohort = df_cohort[
        df_cohort["firstdisbursementdate"].astype(str).str.lower() != "nan"
    ].copy()

    logger.info(
        f"  • Filtered unoriginated noise. Core active footprint size: {len(df_cohort):,} loans."
    )

    # 2. High-Integrity Compound Key Deduplication Drop
    df_cohort["borrzip"] = df_cohort["borrzip"].fillna("").astype(str).str.strip()
    df_cohort["naicscode"] = df_cohort["naicscode"].fillna("").astype(str).str.strip()
    logical_keys = ["approvaldate", "borrzip", "terminmonths", "naicscode"]
    df_cohort = df_cohort.drop_duplicates(
        subset=logical_keys, keep="first"
    ).reset_index(drop=True)

    # 3. Dynamic Spatial Mapping Handshake
    logger.info("  • Invoking GeographyDaemon for parallel spatial mapping...")
    df_cohort["approval_year"] = pd.to_datetime(
        df_cohort["approvaldate"], errors="coerce"
    ).dt.year
    df_cohort["approval_year"] = (
        df_cohort["approval_year"].fillna(df_cohort["approvalfy_clean"]).astype(int)
    )

    def resolve_fips_row(row):
        zip_val = row["borrzip"]
        year_val = row["approval_year"]
        if (
            pd.notna(zip_val)
            and str(zip_val).strip() != ""
            and str(zip_val).strip().lower() != "nan"
        ):
            zip_clean = str(zip_val).strip().split(".")[0].zfill(5)
            mappings = geo_daemon.zip_to_fips(zip_clean, year_val)
            if mappings and len(mappings) > 0:
                mappings.sort(key=lambda x: x[1], reverse=True)
                return str(mappings[0][0]).zfill(5)
        fallback_fips = geo_daemon.county_text_to_fips(
            row["projectstate"], row["projectcounty"], year_val
        )
        if fallback_fips:
            return str(fallback_fips).zfill(5)
        return "00000"

    df_cohort["standardized_fips"] = df_cohort.apply(resolve_fips_row, axis=1)

    # 4. Programmatic High-Velocity Vectorized NAICS Extraction (No Truncation)
    logger.info(
        "  • Invoking vectorized daemon engine to lock down 4-digit and 3-digit credit risk groups..."
    )
    df_cohort["naics_4d"], df_cohort["naics_3d"] = (
        geo_daemon.resolve_credit_risk_naics_batch(df_cohort["naicscode"])
    )

    # 5. Neutral Survival Engineering Engine (PROJECT NEUTRAL - NO RIGHT CENSORING MARKS)
    logger.info("  • Pre-calculating raw continuous timeline durations...")
    for d_col in [
        "asofdate",
        "approvaldate",
        "firstdisbursementdate",
        "paidinfulldate",
        "chargeoffdate",
    ]:
        df_cohort[d_col] = pd.to_datetime(df_cohort[d_col], errors="coerce")

    dataset_end = df_cohort["asofdate"].max()
    end_point = np.where(
        df_cohort["chargeoffdate"].notna(),
        df_cohort["chargeoffdate"],
        np.where(
            df_cohort["paidinfulldate"].notna(),
            df_cohort["paidinfulldate"],
            dataset_end,
        ),
    )
    end_point = pd.to_datetime(end_point)

    # Compute the full, raw un-censored lifetime observed in months
    delta_days = (end_point - df_cohort["firstdisbursementdate"]).dt.days
    df_cohort["survival_months_raw"] = np.maximum(delta_days / 30.4375, 0.1)

    # 6. Commit Project-Neutral Core Dataframe to SQL Disk Space
    df_cohort = df_cohort.drop(columns=helper_cols, errors="ignore")
    df_cohort = df_cohort.drop(columns=["approval_year"], errors="ignore")

    # Cast dates back to readable standard string fields for clean SQLite text optimization
    for d_col in [
        "asofdate",
        "approvaldate",
        "firstdisbursementdate",
        "paidinfulldate",
        "chargeoffdate",
    ]:
        df_cohort[d_col] = df_cohort[d_col].dt.strftime("%Y-%m-%d")

    logger.info(
        f"Writing neutral analytical cohort table '{COHORT_TABLE}' to SQL storage..."
    )
    df_cohort.to_sql(COHORT_TABLE, conn, if_exists="replace", index=False)

    # -----------------------------------------------------------------
    # PHASE 6: HIGH-PERFORMANCE B-TREE DATABASE INDEXES
    # -----------------------------------------------------------------
    logger.info("Compiling high-velocity structural relational indexing systems...")
    cursor = conn.cursor()

    # Raw Master Indices
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_m_naics2 ON {MASTER_TABLE}(naics2digit);"
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_m_fy ON {MASTER_TABLE}(approvalfy);"
    )

    # Pristine Core Analytical Modeling Indices
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_c_naics4d ON {COHORT_TABLE}(naics_4d);"
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_c_naics3d ON {COHORT_TABLE}(naics_3d);"
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_c_fips ON {COHORT_TABLE}(standardized_fips);"
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_c_fy ON {COHORT_TABLE}(approvalfy);"
    )

    conn.commit()
    conn.close()
    geo_daemon.close()
    logger.info("--- 🚀 SUCCESS: UNIFIED WAREHOUSE ENGINE EXECUTION SYNC COMPLETE ---")


if __name__ == "__main__":
    main()

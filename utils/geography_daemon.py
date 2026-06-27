import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import pandas as pd
import numpy as np
import re


class GeographyDaemon:
    """
    Centralized spatial and industry orchestration engine for temporal ZIP-to-FIPS translations,
    FIPS retirement tracking, and longitudinal NAICS industry crosswalk matching layers.
    """

    def __init__(self, database_dir: Optional[Union[str, Path]] = None):
        root_dir = Path(__file__).resolve().parent.parent
        if database_dir:
            self.db_dir = Path(database_dir)
        else:
            self.db_dir = root_dir / "databases"

        self.spatial_db_path = self.db_dir / "spatial_crosswalk.db"
        if not self.spatial_db_path.exists():
            raise FileNotFoundError(
                f"Core Spatial Database absent at structural location: {self.spatial_db_path}"
            )
        self.conn = sqlite3.connect(self.spatial_db_path)

    def close(self):
        if self.conn:
            self.conn.close()

    def get_active_fips(self, fips: str, operational_year: int) -> str:
        """Recursively evaluates historical boundary retirement chains."""
        fips_clean = str(fips).strip().zfill(5)
        cursor = self.conn.cursor()
        query = "SELECT date_retired, successor_fips FROM dim_geography_fips WHERE standardized_fips = ?;"
        cursor.execute(query, (fips_clean,))
        row = cursor.fetchone()
        if not row:
            return fips_clean

        date_retired, successor_fips = row
        if date_retired != 9999 and int(operational_year) >= int(date_retired):
            if successor_fips:
                return self.get_active_fips(successor_fips, operational_year)
        return fips_clean

    def zip_to_fips(self, zip_code: str, target_year: int) -> List[Tuple[str, float]]:
        """Resolves a 5-digit ZIP code to historically accurate Standardized FIPS code(s)."""
        if pd.isna(zip_code) or not zip_code:
            return []

        zip_clean = re.split(r"\.", str(zip_code).strip())[0].zfill(5)
        year_target = int(target_year)

        cursor = self.conn.cursor()
        query = "SELECT standardized_fips, allocation_factor FROM map_zip_to_fips WHERE zip_code = ? AND vintage_year = ?;"
        cursor.execute(query, (zip_clean, year_target))
        rows = cursor.fetchall()

        if not rows:
            fallback_query = """
                SELECT standardized_fips, allocation_factor FROM map_zip_to_fips 
                WHERE zip_code = ? 
                ORDER BY ABS(vintage_year - ?) ASC 
                LIMIT 5;
            """
            cursor.execute(fallback_query, (zip_clean, year_target))
            rows = cursor.fetchall()
            if not rows:
                return []

        resolved_mappings = []
        for fips, alloc in rows:
            active_fips = self.get_active_fips(fips, year_target)
            resolved_mappings.append((active_fips, float(alloc)))
        return resolved_mappings

    def county_text_to_fips(
        self, state: str, county_name: str, target_year: int
    ) -> Optional[str]:
        """Resolves 'ST_COUNTYNAME' strings into active FIPS codes."""
        if pd.isna(state) or pd.isna(county_name):
            return None

        st_clean = str(state).strip().upper()
        co_clean = str(county_name).strip().upper()
        co_clean = re.sub(r"[^A-Z0-9]", "", co_clean)
        lookup_key = f"{st_clean}_{co_clean}"

        cursor = self.conn.cursor()
        query = "SELECT standardized_fips FROM map_county_text_to_fips WHERE lookup_key = ?;"
        cursor.execute(query, (lookup_key,))
        row = cursor.fetchone()

        if not row:
            prefix_query = "SELECT standardized_fips FROM map_county_text_to_fips WHERE lookup_key LIKE ? LIMIT 1;"
            cursor.execute(prefix_query, (f"{lookup_key}%",))
            row = cursor.fetchone()
            if not row:
                return None
        return self.get_active_fips(row[0], target_year)

    def normalize_naics_code(self, raw_naics: Union[str, float, int]) -> Optional[str]:
        """
        Intercepts and repairs SQLite float casting corruption (e.g., 722511.0 -> '722511').
        Guarantees returned tokens are numeric strings truncated between 2 and 6 digits.
        """
        if pd.isna(raw_naics) or str(raw_naics).strip() == "":
            return None

        # Clear float formatting suffix
        naics_str = str(raw_naics).strip()
        if "." in naics_str:
            naics_str = naics_str.split(".")[0]

        # Clean non-numeric anomalies
        naics_clean = re.sub(r"\D", "", naics_str)

        if len(naics_clean) < 2:
            return None

        # Truncate to maximum standard census width
        return naics_clean[:6]

    def resolve_historical_naics_epoch(
        self, cleaned_naics: str, loan_year: int, target_qcew_year: int
    ) -> str:
        """
        Maintains structural tracking through multi-year industry classification epochs.
        If your mapping schema doesn't contain a bridge, it steps down the hierarchy
        (e.g., 6-digit -> 3-digit) to preserve spatial consistency.
        """
        if int(loan_year) == int(target_qcew_year) or len(cleaned_naics) <= 2:
            return cleaned_naics

        # This structural hook uses map_source_to_fips or a new crosswalk table
        # (e.g., dim_naics_crosswalk) inside spatial_crosswalk.db
        cursor = self.conn.cursor()

        # Verify if crosswalk table exists first to avoid crashing existing deployments
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dim_naics_crosswalk';"
        )
        if not cursor.fetchone():
            return cleaned_naics  # Fail-safe fallback to base code if mapping table isn't built yet

        query = """
            SELECT target_naics FROM dim_naics_crosswalk 
            WHERE source_naics = ? AND source_year = ? AND target_year = ?;
        """
        cursor.execute(query, (cleaned_naics, int(loan_year), int(target_qcew_year)))
        row = cursor.fetchone()

        if row and row[0]:
            return str(row[0])

        # Fallback step: Prune rightmost digit to attempt a higher structural aggregate match (e.g., 6 -> 5 -> 4 -> 3-digit)
        return self.resolve_historical_naics_epoch(
            cleaned_naics[:-1], loan_year, target_qcew_year
        )

    def resolve_credit_risk_naics_batch(
        self, naics_series: pd.Series
    ) -> Tuple[pd.Series, pd.Series]:
        """
        High-velocity vectorized extraction engine designed specifically for credit risk modeling.
        Bypasses BLS QCEW cell-suppression truncation logic to preserve detailed
        4-digit and 3-digit industry classifications across long historical panels.

        Parameters:
        -----------
        naics_series : pd.Series
            The raw, uncleaned NAICS series straight from the database extract (supports floats/strings).

        Returns:
        --------
        Tuple[pd.Series, pd.Series]
            A pristine (naics_4d, naics_3d) series pair formatted as zero-padded, clean text strings.
        """
        # 1. Vectorized String Coercion & Cleanup (Handles NaN and Float Casting Bugs natively)
        s_str = naics_series.fillna("999999").astype(str).str.strip()

        # Vectorized split to instantly drop trailing float decimals (.0) across all records
        s_str = s_str.str.split(".").str[0]

        # Vectorized regex substitution to strip any non-numeric noise tokens
        s_str = s_str.str.replace(r"\D", "", regex=True)

        # Explicit zero-padding fallback handle for short or malformed character segments
        s_str = s_str.str.pad(width=6, side="right", fillchar="0")

        # 2. Vectorized Slicing to Lock Down Credit Hazard Segments (No Row-by-Row Loops)
        naics_4d = s_str.str[:4]
        naics_3d = s_str.str[:3]

        # Standardize empty placeholder definitions uniformly across the database layout
        naics_4d = np.where(
            naics_4d.str.startswith("9999") | (naics_4d == ""), "9999", naics_4d
        )
        naics_3d = np.where(
            naics_3d.str.startswith("999") | (naics_3d == ""), "999", naics_3d
        )

        return pd.Series(naics_4d), pd.Series(naics_3d)

    def attach_fips_and_naics_to_dataframe(
        self,
        df: pd.DataFrame,
        zip_col: str,
        state_col: str,
        county_col: str,
        naics_col: str,
        year_col: str,
        fips_output_col: str = "standardized_fips",
        naics_output_col: str = "standardized_naics",
    ) -> pd.DataFrame:
        """
        Dual-key execution architecture. Resolves clean geography spatial tracking
        and strings out float-corrupted industry fields simultaneously.
        """

        def _resolve_row(row):
            # 1. Geographic Resolution Layer
            fips_res = None
            zip_val = row[zip_col]
            year_val = row[year_col]

            if pd.notna(zip_val) and str(zip_val).strip() != "":
                mappings = self.zip_to_fips(zip_val, year_val)
                if mappings:
                    mappings.sort(key=lambda x: x[1], reverse=True)
                    fips_res = mappings[0][0]

            if not fips_res:
                fips_res = self.county_text_to_fips(
                    row[state_col], row[county_col], year_val
                )

            # 2. Industry Resolution Layer
            naics_res = self.normalize_naics_code(row[naics_col])

            return pd.Series([fips_res, naics_res])

        df[[fips_output_col, naics_output_col]] = df.apply(_resolve_row, axis=1)
        return df

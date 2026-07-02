import sqlite3
import json
import datetime
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Union, List, Dict, Tuple


class MacroFeatureEngineV2:
    """
    Enterprise-Grade Hyperlocal Macro Feature Factory.

    Consumes spatial-temporal keys and extracts slow-moving economic indicators
    from IRS SOI, BLS QCEW, BLS LAUS, and Census QWI database warehouses.
    Operates strictly as a pure-data calculator decoupled from presentation views.
    """

    # Structural non-MSA credit risk governance parameters
    STRATEGY_COUNTY_ONLY = "COUNTY_ONLY"
    STRATEGY_STATE_AVERAGE = "STATE_AVERAGE"
    STRATEGY_RAISE_EXCEPTION = "RAISE_EXCEPTION"

    def __init__(
        self, geography_daemon=None, database_dir: Optional[Union[str, Path]] = None
    ):
        """
        Initializes the engine, maps file dependencies, and detects database horizons.
        """
        self.geo_daemon = geography_daemon

        # Step up from utility paths to access the underlying warehouse directory
        root_dir = Path(__file__).resolve().parent.parent
        self.db_dir = Path(database_dir) if database_dir else root_dir / "databases"

        # Explicit portable SQLite warehouse paths
        self.irs_path = self.db_dir / "irs_county_soi.db"
        self.qcew_path = self.db_dir / "bls_qcew_industry.db"
        self.laus_path = self.db_dir / "bls_laus_macro.db"
        self.msa_json_path = self.db_dir / "msa_county_map.json"
        self.fred_path = self.db_dir / "fred_macro_indicators.db"
        self.census_state_path = self.db_dir / "census_state_macro.db"

        # Enforce O(1) crosswalk asset validation before initializing engine track
        if not self.msa_json_path.exists():
            raise FileNotFoundError(
                f"❌ Required warehouse asset missing at: {self.msa_json_path}"
            )

        with open(self.msa_json_path, "r", encoding="utf-8") as f:
            self.msa_map = json.load(f)

        # Dynamically sense the right-censored temporal ceiling for IRS tax fields
        self.max_irs_year = self._detect_database_ceiling(
            self.irs_path, "county_economics", "calendar_year"
        )
        print(
            f"⚙️ Engine initialized cleanly. Detected right-censored IRS ceiling as tax year: {self.max_irs_year}"
        )

    def _detect_database_ceiling(
        self, db_path: Path, table_name: str, year_col: str
    ) -> int:
        """
        Queries the absolute maximum record year present on disk to manage lag calculations.
        """
        if not db_path.exists():
            return 2022
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT MAX({year_col}) FROM {table_name};")
            fetched = cursor.fetchone()
            return int(fetched[0]) if fetched and fetched[0] is not None else 2022
        except Exception:
            return 2022
        finally:
            conn.close()

    def _calculate_relative_temporal_target(self, loan_vintage_year: int) -> int:
        """
        Aligns historical loan cohorts to historical database releases.
        Prevents forward-looking information bias by applying the calculated data lag.
        """
        current_year = datetime.datetime.now().year
        relative_lag = current_year - self.max_irs_year
        return int(loan_vintage_year) - relative_lag

    def _get_msa_components(
        self, county_fips: str, strategy: str
    ) -> Tuple[List[str], str]:
        """
        Applies spatial crosswalk routing to manage non-MSA rural parameters.
        Enforces credit governance contracts for rural jurisdictions.
        """
        fips_clean = str(county_fips).strip().zfill(5)
        county_node = self.msa_map.get(fips_clean)

        # If the county belongs to a verified MSA, route all component FIPS codes
        if county_node and county_node.get("msa_code"):
            return county_node["component_fips"], "TRUE_METRO"

        # Handle rural territories using the specified credit policy strategy
        if strategy == self.STRATEGY_COUNTY_ONLY:
            return [fips_clean], "RURAL_COUNTY_ONLY"
        elif strategy == self.STRATEGY_STATE_AVERAGE:
            return [], "RURAL_STATE_AVERAGE"
        elif strategy == self.STRATEGY_RAISE_EXCEPTION:
            raise ValueError(
                f"🚨 Policy Exception: FIPS {fips_clean} is a rural territory. Processing blocked."
            )
        else:
            raise ValueError(
                f"❌ Invalid non_msa_strategy parameter provided: {strategy}"
            )

    def compute_passive_wealth_profile(
        self, county_fips: str, loan_vintage_year: int, non_msa_strategy: str
    ) -> Dict[str, Union[float, str]]:
        """
        Extracts Passive Wealth Depth and Filer Volume Dynamics from irs_county_soi.db.

        Dynamically aligns temporal targets and executes spatial aggregations based
        on the mandated credit policy strategy.
        """
        if not self.irs_path.exists():
            return {
                "macro_wealth_cushion": 0.0,
                "filer_density_velocity": 0.0,
                "household_dependency_ratio": 0.0,
                "spatial_governance_flag": "DATABASE_MISSING",
            }

        fips_clean = str(county_fips).strip().zfill(5)
        component_fips, spatial_flag = self._get_msa_components(
            fips_clean, non_msa_strategy
        )
        target_year = self._calculate_relative_temporal_target(loan_vintage_year)

        conn = sqlite3.connect(self.irs_path)
        try:
            # Handle rural territories using state-wide spatial pooling
            if spatial_flag == "RURAL_STATE_AVERAGE":
                state_prefix = fips_clean[:2] + "%"
                query = """
                    SELECT 
                        SUM(wages_and_salaries) as total_wages, 
                        SUM(dividends_received) as total_dividends, 
                        SUM(interest_received) as total_interest, 
                        SUM(total_returns) as total_returns, 
                        SUM(total_exemptions) as total_exemptions 
                    FROM county_economics 
                    WHERE county_fips LIKE ? AND calendar_year = ?
                """
                df_curr = pd.read_sql_query(
                    query, conn, params=(state_prefix, target_year)
                )

                # Fetch 5-year historical lag to calculate structural migration velocity
                query_lag = """
                    SELECT SUM(total_returns) as returns_lag 
                    FROM county_economics 
                    WHERE county_fips LIKE ? AND calendar_year = ?
                """
                df_lag = pd.read_sql_query(
                    query_lag, conn, params=(state_prefix, target_year - 5)
                )

            # Handle standard MSA or single-county structural footprints
            else:
                placeholders = ",".join(["?"] * len(component_fips))
                query = f"""
                    SELECT 
                        SUM(wages_and_salaries) as total_wages, 
                        SUM(dividends_received) as total_dividends, 
                        SUM(interest_received) as total_interest, 
                        SUM(total_returns) as total_returns, 
                        SUM(total_exemptions) as total_exemptions 
                    FROM county_economics 
                    WHERE county_fips IN ({placeholders}) AND calendar_year = ?
                """
                df_curr = pd.read_sql_query(
                    query, conn, params=component_fips + [target_year]
                )

                query_lag = f"""
                    SELECT SUM(total_returns) as returns_lag 
                    FROM county_economics 
                    WHERE county_fips IN ({placeholders}) AND calendar_year = ?
                """
                df_lag = pd.read_sql_query(
                    query_lag, conn, params=component_fips + [target_year - 5]
                )
        finally:
            conn.close()

        # Handle missing data or data gaps safely
        if (
            df_curr.empty
            or pd.isna(df_curr["total_returns"].iloc[0])
            or df_curr["total_returns"].iloc[0] == 0
        ):
            return {
                "macro_wealth_cushion": 0.0,
                "filer_density_velocity": 0.0,
                "household_dependency_ratio": 0.0,
                "spatial_governance_flag": "DATA_GAP_FALLBACK",
            }

        # Extract scalar results from the aggregate queries safely
        w = (
            float(df_curr["total_wages"].iloc[0])
            if pd.notna(df_curr["total_wages"].iloc[0])
            else 0.0
        )
        d = (
            float(df_curr["total_dividends"].iloc[0])
            if pd.notna(df_curr["total_dividends"].iloc[0])
            else 0.0
        )
        i = (
            float(df_curr["total_interest"].iloc[0])
            if pd.notna(df_curr["total_interest"].iloc[0])
            else 0.0
        )
        r = float(df_curr["total_returns"].iloc[0])
        e = (
            float(df_curr["total_exemptions"].iloc[0])
            if pd.notna(df_curr["total_exemptions"].iloc[0])
            else 0.0
        )

        r_lag = (
            float(df_lag["returns_lag"].iloc[0])
            if not df_lag.empty and pd.notna(df_lag["returns_lag"].iloc[0])
            else r
        )

        # Return calculated structural wealth metrics
        return {
            "macro_wealth_cushion": (d + i) / w if w > 0 else 0.0,
            "filer_density_velocity": (r - r_lag) / r_lag if r_lag > 0 else 0.0,
            "household_dependency_ratio": e / r if r > 0 else 0.0,
            "spatial_governance_flag": spatial_flag,
        }

    def compute_labor_and_saturation_profile(
        self,
        county_fips: str,
        loan_vintage_year: int,
        naics_4d: str,
        non_msa_strategy: str,
    ) -> Dict[str, float]:
        """
        Extracts Workforce Stability Trajectories and Industry Saturation Profiles.

        Pushes NAICS prefix lookups to the database disk layer via indexed SQL LIKE
        operators to avoid unbounded memory scans and secure small audit logs.
        """
        if not self.laus_path.exists() or not self.qcew_path.exists():
            return {
                "labor_pool_structural_friction": 0.0,
                "industry_market_saturation_lq": 0.0,
            }

        fips_clean = str(county_fips).strip().zfill(5)
        naics_clean = str(naics_4d).strip().zfill(4)
        component_fips, spatial_flag = self._get_msa_components(
            fips_clean, non_msa_strategy
        )
        target_year = self._calculate_relative_temporal_target(loan_vintage_year)
        year_start = target_year - 4

        # Build pristine state-county text pairs matching database padding rules
        geo_pairs = [(f[:2].zfill(2), f[2:].zfill(3)) for f in component_fips]

        # =====================================================================
        # 1. OPTIMIZED LAUS WORKFORCE PROFILE EXECUTION
        # =====================================================================
        conn_laus = sqlite3.connect(self.laus_path)
        try:
            if spatial_flag == "RURAL_STATE_AVERAGE":
                state_prefix = fips_clean[:2]
                query_laus = """
                    SELECT value as labor_force FROM laus_monthly_records 
                    WHERE state_fips = ? AND measure_code = '06' AND year BETWEEN ? AND ?
                """
                df_laus = pd.read_sql_query(
                    query_laus,
                    conn_laus,
                    params=(state_prefix, year_start, target_year),
                )
            else:
                pair_placeholders = ",".join(["(?, ?)"] * len(geo_pairs))
                query_laus = f"""
                    SELECT value as labor_force FROM laus_monthly_records 
                    WHERE (state_fips, county_fips) IN ({pair_placeholders}) 
                      AND measure_code = '06' AND year BETWEEN ? AND ?
                """
                flat_params_laus = []
                for state, county in geo_pairs:
                    flat_params_laus.extend([state, county])
                flat_params_laus.extend([year_start, target_year])
                df_laus = pd.read_sql_query(
                    query_laus, conn_laus, params=flat_params_laus
                )
        finally:
            conn_laus.close()

        # Compute coefficient of variation (CV) for structural friction
        if not df_laus.empty and df_laus["labor_force"].mean() > 0:
            labor_friction_cv = (
                df_laus["labor_force"].std() / df_laus["labor_force"].mean()
            )
        else:
            labor_friction_cv = 0.0

        # =====================================================================
        # 2. OPTIMIZED QCEW INDUSTRY SATURATION EXECUTION
        # =====================================================================
        conn_qcew = sqlite3.connect(self.qcew_path)

        # Format the wildcard parameter for strict 4-digit prefix disk matching
        naics_wildcard = f"{naics_clean}%"

        try:
            # Query ONLY the total national sum and the specific industry target on disk
            query_nat = """
                SELECT 
                    SUM(CASE WHEN naics_code LIKE ? THEN establishment_count ELSE 0 END) as nat_sector,
                    SUM(establishment_count) as nat_total
                FROM qcew_annual_industry_records 
                WHERE own_code = '5' AND year = ?
            """
            df_nat = pd.read_sql_query(
                query_nat, conn_qcew, params=(naics_wildcard, target_year)
            )

            if spatial_flag == "RURAL_STATE_AVERAGE":
                state_prefix = fips_clean[:2] + "%"
                query_loc = """
                    SELECT 
                        SUM(CASE WHEN naics_code LIKE ? THEN establishment_count ELSE 0 END) as loc_sector,
                        SUM(establishment_count) as loc_total
                    FROM qcew_annual_industry_records 
                    WHERE standardized_fips LIKE ? AND own_code = '5' AND year = ?
                """
                df_loc = pd.read_sql_query(
                    query_loc,
                    conn_qcew,
                    params=(naics_wildcard, state_prefix, target_year),
                )
            else:
                placeholders = ",".join(["?"] * len(component_fips))
                query_loc = f"""
                    SELECT 
                        SUM(CASE WHEN naics_code LIKE ? THEN establishment_count ELSE 0 END) as loc_sector,
                        SUM(establishment_count) as loc_total
                    FROM qcew_annual_industry_records 
                    WHERE standardized_fips IN ({placeholders}) AND own_code = '5' AND year = ?
                """
                df_loc = pd.read_sql_query(
                    query_loc,
                    conn_qcew,
                    params=[naics_wildcard] + component_fips + [target_year],
                )
        finally:
            conn_qcew.close()

        # =====================================================================
        # 3. DIRECT SCALAR EXTRACTION
        # =====================================================================
        nat_sector = (
            float(df_nat["nat_sector"].iloc[0])
            if not df_nat.empty and pd.notna(df_nat["nat_sector"].iloc[0])
            else 0.0
        )
        nat_total = (
            float(df_nat["nat_total"].iloc[0])
            if not df_nat.empty and pd.notna(df_nat["nat_total"].iloc[0])
            else 1.0
        )

        loc_sector = (
            float(df_loc["loc_sector"].iloc[0])
            if not df_loc.empty and pd.notna(df_loc["loc_sector"].iloc[0])
            else 0.0
        )
        loc_total = (
            float(df_loc["loc_total"].iloc[0])
            if not df_loc.empty and pd.notna(df_loc["loc_total"].iloc[0])
            else 0.0
        )

        national_share = nat_sector / nat_total if nat_total > 0 else 0.0
        local_share = loc_sector / loc_total if loc_total > 0 else 0.0

        industry_market_saturation_lq = (
            local_share / national_share if national_share > 0 else 0.0
        )

        return {
            "labor_pool_structural_friction": float(labor_friction_cv),
            "industry_market_saturation_lq": float(industry_market_saturation_lq),
        }

    def compute_advanced_structural_profile(
        self, county_fips: str, loan_vintage_year: int, non_msa_strategy: str
    ) -> Dict[str, float]:
        """
        Extracts Advanced Regional Structural and Disconnect Profiles from
        bls_qcew_industry.db and irs_county_soi.db.

        FIXED: Applies strict length filtering to prevent hierarchical row
        duplication on disk, pruning query rows from 15,000+ down to ~3,000.
        """
        if not self.qcew_path.exists() or not self.irs_path.exists():
            return {
                "wage_diversification_index": 1.0,
                "wage_to_filer_disconnect_index": 0.0,
            }

        fips_clean = str(county_fips).strip().zfill(5)
        component_fips, spatial_flag = self._get_msa_components(
            fips_clean, non_msa_strategy
        )
        target_year = self._calculate_relative_temporal_target(loan_vintage_year)

        # =====================================================================
        # 1. LOCAL INDUSTRY WAGE DIVERSIFICATION INDEX (QCEW HHI)
        # =====================================================================
        conn_qcew = sqlite3.connect(self.qcew_path)
        try:
            if spatial_flag == "RURAL_STATE_AVERAGE":
                state_prefix = fips_clean[:2] + "%"
                query_wage = """
                    SELECT total_annual_wages FROM qcew_annual_industry_records 
                    WHERE standardized_fips LIKE ? AND own_code = '5' AND year = ? 
                      AND LENGTH(naics_code) = 4 -- STRIPS OUT 3, 5, AND 6 DIGIT DUPLICATES
                """
                df_wages = pd.read_sql_query(
                    query_wage, conn_qcew, params=(state_prefix, target_year)
                )
            else:
                placeholders = ",".join(["?"] * len(component_fips))
                query_wage = f"""
                    SELECT total_annual_wages FROM qcew_annual_industry_records 
                    WHERE standardized_fips IN ({placeholders}) AND own_code = '5' AND year = ? 
                      AND LENGTH(naics_code) = 4 -- STRIPS OUT 3, 5, AND 6 DIGIT DUPLICATES
                """
                df_wages = pd.read_sql_query(
                    query_wage, conn_qcew, params=component_fips + [target_year]
                )
        finally:
            conn_qcew.close()

        # Compute clean, non-duplicated HHI payroll metrics
        if not df_wages.empty and df_wages["total_annual_wages"].sum() > 0:
            total_regional_payroll = df_wages["total_annual_wages"].sum()
            shares_squared = (
                df_wages["total_annual_wages"] / total_regional_payroll
            ) ** 2
            hhi = shares_squared.sum()
            wage_diversification_index = 1.0 - hhi
        else:
            wage_diversification_index = 1.0

        # =====================================================================
        # 2. THE WAGE-TO-FILER DISCONNECT INDEX (IRS VS BLS LONGITUDINAL)
        # =====================================================================
        conn_irs = sqlite3.connect(self.irs_path)
        conn_qcew = sqlite3.connect(self.qcew_path)
        try:
            if spatial_flag == "RURAL_STATE_AVERAGE":
                state_p = fips_clean[:2] + "%"
                irs_c = pd.read_sql_query(
                    "SELECT SUM(wages_and_salaries) FROM county_economics WHERE county_fips LIKE ? AND calendar_year = ?",
                    conn_irs,
                    params=(state_p, target_year),
                )
                bls_c = pd.read_sql_query(
                    "SELECT SUM(total_annual_wages) FROM qcew_annual_industry_records WHERE standardized_fips LIKE ? AND own_code = '5' AND year = ? AND LENGTH(naics_code) = 2",
                    conn_qcew,
                    params=(state_p, target_year),
                )
                irs_l = pd.read_sql_query(
                    "SELECT SUM(wages_and_salaries) FROM county_economics WHERE county_fips LIKE ? AND calendar_year = ?",
                    conn_irs,
                    params=(state_p, target_year - 5),
                )
                bls_l = pd.read_sql_query(
                    "SELECT SUM(total_annual_wages) FROM qcew_annual_industry_records WHERE standardized_fips LIKE ? AND own_code = '5' AND year = ? AND LENGTH(naics_code) = 2",
                    conn_qcew,
                    params=(state_p, target_year - 5),
                )
            else:
                placeholders = ",".join(["?"] * len(component_fips))
                irs_c = pd.read_sql_query(
                    f"SELECT SUM(wages_and_salaries) FROM county_economics WHERE county_fips IN ({placeholders}) AND calendar_year = ?",
                    conn_irs,
                    params=component_fips + [target_year],
                )
                bls_c = pd.read_sql_query(
                    f"SELECT SUM(total_annual_wages) FROM qcew_annual_industry_records WHERE standardized_fips IN ({placeholders}) AND own_code = '5' AND year = ? AND LENGTH(naics_code) = 2",
                    conn_qcew,
                    params=component_fips + [target_year],
                )
                irs_l = pd.read_sql_query(
                    f"SELECT SUM(wages_and_salaries) FROM county_economics WHERE county_fips IN ({placeholders}) AND calendar_year = ?",
                    conn_irs,
                    params=component_fips + [target_year - 5],
                )
                bls_l = pd.read_sql_query(
                    f"SELECT SUM(total_annual_wages) FROM qcew_annual_industry_records WHERE standardized_fips IN ({placeholders}) AND own_code = '5' AND year = ? AND LENGTH(naics_code) = 2",
                    conn_qcew,
                    params=component_fips + [target_year - 5],
                )
        finally:
            conn_irs.close()
            conn_qcew.close()

        # Extract native scalars cleanly via .squeeze()
        ic = (
            float(irs_c.squeeze())
            if not irs_c.empty and pd.notna(irs_c.squeeze())
            else 0.0
        )
        bc = (
            float(bls_c.squeeze())
            if not bls_c.empty and pd.notna(bls_c.squeeze())
            else 0.0
        )
        il = (
            float(irs_l.squeeze())
            if not irs_l.empty and pd.notna(irs_l.squeeze())
            else ic
        )
        bl = (
            float(bls_l.squeeze())
            if not bls_l.empty and pd.notna(bls_l.squeeze())
            else bc
        )

        irs_wage_growth = (ic - il) / il if il > 0 else 0.0
        bls_wage_growth = (bc - bl) / bl if bl > 0 else 0.0

        return {
            "wage_diversification_index": float(wage_diversification_index),
            "wage_to_filer_disconnect_index": float(irs_wage_growth - bls_wage_growth),
        }

    def compute_sovereign_state_shock_profile(
        self, county_fips: str, loan_vintage_year: int
    ) -> Dict:
        """
        Extracts Sovereign and State-Level Systemic Risk Anchors from FRED and Census.

        Evaluates regional macro indexes (PHCI), corporate yield spreads, and
        workforce turnover parameters while preventing eager-casting crashes.
        """
        import logging

        logger = logging.getLogger(__name__)

        fips_clean = str(county_fips).strip().zfill(5)
        state_fips = fips_clean[:2]
        target_year = self._calculate_relative_temporal_target(loan_vintage_year)

        # O(1) Local State Postal Crosswalk Mapper
        state_map = {
            "01": "AL",
            "02": "AK",
            "04": "AZ",
            "05": "AR",
            "06": "CA",
            "08": "CO",
            "09": "CT",
            "10": "DE",
            "12": "FL",
            "13": "GA",
            "15": "HI",
            "16": "ID",
            "17": "IL",
            "18": "IN",
            "19": "IA",
            "20": "KS",
            "21": "KY",
            "22": "LA",
            "23": "ME",
            "24": "MD",
            "25": "MA",
            "26": "MI",
            "27": "MN",
            "28": "MS",
            "29": "MO",
            "30": "MT",
            "31": "NE",
            "32": "NV",
            "33": "NH",
            "34": "NJ",
            "35": "NM",
            "36": "NY",
            "37": "NC",
            "38": "ND",
            "39": "OH",
            "40": "OK",
            "41": "OR",
            "42": "PA",
            "44": "RI",
            "45": "SC",
            "46": "SD",
            "47": "TN",
            "48": "TX",
            "49": "UT",
            "50": "VT",
            "51": "VA",
            "53": "WA",
            "54": "WV",
            "55": "WI",
            "56": "WY",
        }
        state_postal = state_map.get(state_fips, "TX")
        phci_series = f"{state_postal}PHCI"

        # Safe transactional initialization baselines
        state_momentum, yield_spread, sentiment = 0.0, 0.25, 70.0

        # =====================================================================
        # 1. SYSTEMIC MACRO SHOCK SEEDING (FRED)
        # =====================================================================
        if self.fred_path.exists():
            conn_fred = sqlite3.connect(self.fred_path)
            try:
                pc = pd.read_sql_query(
                    "SELECT value FROM fred_macro_indicators WHERE UPPER(series_id) = UPPER(?) AND year = ? AND month = 12",
                    conn_fred,
                    params=(phci_series, target_year),
                )
                yc = pd.read_sql_query(
                    "SELECT value FROM fred_macro_indicators WHERE UPPER(series_id) = 'T10Y2Y' AND year = ? AND month = 12",
                    conn_fred,
                    params=(target_year,),
                )
                sc = pd.read_sql_query(
                    "SELECT value FROM fred_macro_indicators WHERE UPPER(series_id) = 'UMCSENT' AND year = ? AND month = 12",
                    conn_fred,
                    params=(target_year,),
                )
                pl = pd.read_sql_query(
                    "SELECT value FROM fred_macro_indicators WHERE UPPER(series_id) = ? AND year = ? AND month = 12",
                    conn_fred,
                    params=(phci_series, target_year - 1),
                )

                # FIXED: Evaluates df.empty strictly BEFORE casting to prevent TypeErrors
                p_c_val = float(pc.squeeze()) if not pc.empty else None
                p_l_val = float(pl.squeeze()) if not pl.empty else None

                # Process calculations only if database contains valid vectors
                if p_c_val is not None and p_l_val is not None:
                    state_momentum = (
                        (p_c_val - p_l_val) / p_l_val if p_l_val > 0 else 0.0
                    )
                else:
                    state_momentum = 0.0
                    logger.warning(
                        f"FRED series data missing for {phci_series} in target years."
                    )

                yield_spread = float(yc.squeeze()) if not yc.empty else 0.25
                sentiment = float(sc.squeeze()) if not sc.empty else 70.0

            except Exception as e:
                logger.error(
                    f"Execution failure inside FRED processing engine: {str(e)}"
                )
                pass
            finally:
                conn_fred.close()

        # =====================================================================
        # 2. STATE CHURN & LABOUR TURNOVER SHOCKS (CENSUS QWI)
        # =====================================================================
        turnover, job_flows = 0.0, 0
        if self.census_state_path.exists():
            conn_census = sqlite3.connect(self.census_state_path)
            try:
                qwi = pd.read_sql_query(
                    "SELECT separation_rate, net_job_flow_count FROM census_state_indicators WHERE TRIM(state_fips) = TRIM(?) AND year = ? AND quarter = 4",
                    conn_census,
                    params=(state_fips, target_year),
                )
                if not qwi.empty:
                    turnover = float(qwi["separation_rate"].iloc[0])
                    job_flows = int(qwi["net_job_flow_count"].iloc[0])
            except Exception as e:
                logger.error(
                    f"Execution failure inside Census state processing engine: {str(e)}"
                )
                pass
            finally:
                conn_census.close()

        return {
            "state_coincident_momentum": state_momentum,
            "sovereign_yield_spread": yield_spread,
            "macro_consumer_sentiment": sentiment,
            "state_private_turnover_rate": turnover,
            "state_net_job_flow_count": job_flows,
        }

    def extract_comprehensive_macro_profile(
        self,
        county_fips: str,
        loan_vintage_year: int,
        naics_4d: Optional[str] = None,
        non_msa_strategy: str = "COUNTY_ONLY",
    ) -> Dict[str, Union[float, int, str, None]]:
        """
        PURE DATA GENERATOR (MULTI-TIER GEOGRAPHIC ENTRY GATEWAY).

        Compiles all macro, sovereign, and state shock layers. Automatically
        detects state FIPS strings (ending in '000') to trigger the state-only fork.
        """
        fips_clean = str(county_fips).strip().zfill(5)
        naics_clean = str(naics_4d).strip().zfill(4) if naics_4d else "9999"

        # Enforce State-Only Fork Rule automatically
        is_state_only_query = fips_clean.endswith("000")

        # Gather spatial data layers based on geography routing logic
        if is_state_only_query:
            p_wealth = {}
            l_market = {}
            a_structure = {}
            spatial_flag = "STATE_LEVEL_CORE"
        else:
            p_wealth = self.compute_passive_wealth_profile(
                fips_clean, loan_vintage_year, non_msa_strategy
            )
            l_market = self.compute_labor_and_saturation_profile(
                fips_clean, loan_vintage_year, naics_clean, non_msa_strategy
            )
            a_structure = self.compute_advanced_structural_profile(
                fips_clean, loan_vintage_year, non_msa_strategy
            )
            spatial_flag = p_wealth.get("spatial_governance_flag", "UNKNOWN")

        # Sovereign/state shock profiles calculate natively across both tracks
        shock_profile = self.compute_sovereign_state_shock_profile(
            fips_clean, loan_vintage_year
        )

        # Package data features into a standardized flat parameter payload layout
        profile_data = {
            "target_fips": fips_clean,
            "target_year": loan_vintage_year,
            "target_naics": naics_clean if naics_4d else "GENERAL",
            "spatial_governance_flag": spatial_flag,
            # Dimension 1: Passive Wealth Depth & Migration Profiles
            "macro_wealth_cushion": p_wealth.get("macro_wealth_cushion", None),
            "filer_density_velocity": p_wealth.get("filer_density_velocity", None),
            "household_dependency_ratio": p_wealth.get(
                "household_dependency_ratio", None
            ),
            # Dimension 2: Labor Market Dynamics & Friction
            "labor_pool_structural_friction": l_market.get(
                "labor_pool_structural_friction", None
            ),
            # Dimension 3: Advanced Structure & Disconnect Spreads
            "wage_diversification_index": a_structure.get(
                "wage_diversification_index", None
            ),
            "wage_to_filer_disconnect_index": a_structure.get(
                "wage_to_filer_disconnect_index", None
            ),
            # Dimension 4: Systemic Sovereign & State Shock Anchors
            "state_coincident_momentum": shock_profile.get(
                "state_coincident_momentum", 0.0
            ),
            "sovereign_yield_spread": shock_profile.get("sovereign_yield_spread", 0.0),
            "macro_consumer_sentiment": shock_profile.get(
                "macro_consumer_sentiment", 0.0
            ),
            "state_private_turnover_rate": shock_profile.get(
                "state_private_turnover_rate", 0.0
            ),
            "state_net_job_flow_count": shock_profile.get(
                "state_net_job_flow_count", 0
            ),
        }

        if naics_4d:
            profile_data["industry_market_saturation_lq"] = (
                l_market.get("industry_market_saturation_lq", None)
                if not is_state_only_query
                else None
            )

        return profile_data

    def enrich_portfolio_snapshot(
        self,
        loan_df: pd.DataFrame,
        fips_col: str = "standardized_fips",
        naics_col: str = "naics_4d",
        vintage_year_col: str = "approvalfy",
        non_msa_strategy: str = "COUNTY_ONLY",
    ) -> pd.DataFrame:
        """
        Master Portfolio Pipeline Engine.

        Ingests a DataFrame of loans, groups row items by unique spatial-temporal
        cohort groups to maximize execution speeds, and appends the macro feature suite.
        """
        df_enriched = loan_df.copy()
        df_enriched[fips_col] = (
            df_enriched[fips_col].astype(str).str.strip().str.zfill(5)
        )
        df_enriched[naics_col] = (
            df_enriched[naics_col].astype(str).str.strip().str.zfill(4)
        )

        print(
            f"🚀 Processing portfolio enrichment pipeline for {len(df_enriched):,} loan rows..."
        )

        # Extract unique spatial-temporal blocks to optimize execution speeds
        cohorts = df_enriched[[fips_col, vintage_year_col, naics_col]].drop_duplicates()
        enriched_records = []

        for _, row in cohorts.iterrows():
            fips = row[fips_col]
            v_year = int(row[vintage_year_col])
            naics = row[naics_col]

            try:
                # Trigger the master profile engine natively
                metrics = self.extract_comprehensive_macro_profile(
                    county_fips=fips,
                    loan_vintage_year=v_year,
                    naics_4d=naics if naics != "9999" else None,
                    non_msa_strategy=non_msa_strategy,
                )

                # Force explicit tracking keys into the dictionary payload
                # to guarantee an uncorrupted left-merge execution down-stream
                metrics["cohort_fips_key"] = fips
                metrics["cohort_year_key"] = v_year
                metrics["cohort_naics_key"] = naics
                enriched_records.append(metrics)

            except Exception as e:
                print(f"⚠️ Cohort skipped [{fips} | {v_year} | {naics}]: {str(e)}")
                continue

        if not enriched_records:
            return df_enriched

        # Formulate feature dataframe matrix
        df_features = pd.DataFrame(enriched_records)

        # Drop raw engine metadata labels safely to keep the output dataset clean
        df_features = df_features.drop(
            columns=["target_fips", "target_year", "target_naics"], errors="ignore"
        )

        # Execute clean left-join utilizing synchronized explicit cohort tracking keys
        df_final = df_enriched.merge(
            df_features,
            left_on=[fips_col, vintage_year_col, naics_col],
            right_on=["cohort_fips_key", "cohort_year_key", "cohort_naics_key"],
            how="left",
        ).drop(
            columns=["cohort_fips_key", "cohort_year_key", "cohort_naics_key"],
            errors="ignore",
        )

        print(
            f"✅ Pipeline complete. Advanced features appended to your analytical dataset."
        )
        return df_final

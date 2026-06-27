# =====================================================================
# utils/macro_feature_engine.py (PART 1 OF 2)
# =====================================================================
import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Union
from utils.geography_daemon import GeographyDaemon


class MacroFeatureEngine:
    """
    Structural Macro Feature Engine.
    Ingests local economy indicators and derives stable regional wealth cushions,
    industry market concentrations, and labor pool stability trajectories using
    robust, slow-moving, lagging-insulated parameter design.
    """

    def __init__(self, database_dir: Optional[Union[str, Path]] = None):
        root_dir = Path(__file__).resolve().parent.parent
        self.db_dir = Path(database_dir) if database_dir else root_dir / "databases"
        self.geo_daemon = GeographyDaemon(database_dir=self.db_dir)

        self.irs_path = self.db_dir / "irs_county_soi.db"
        self.qcew_path = self.db_dir / "bls_qcew_industry.db"
        self.laus_path = self.db_dir / "bls_laus_macro.db"

        for path in [self.irs_path, self.qcew_path, self.laus_path]:
            if not path.exists():
                raise FileNotFoundError(
                    f"Required macro warehouse file missing at: {path}"
                )

    def build_structural_irs_profile(self, target_vintage_year: int) -> pd.DataFrame:
        """Extracts county indicators and calculates smooth longitudinal growth trajectories."""
        conn = sqlite3.connect(self.irs_path)
        query = """
            SELECT county_fips, calendar_year, total_returns, wages_and_salaries, dividends_received, interest_received 
            FROM county_economics
        """
        raw_irs = pd.read_sql_query(query, conn)
        conn.close()

        raw_irs["county_fips"] = (
            raw_irs["county_fips"].astype(str).str.strip().str.zfill(5)
        )
        raw_irs["calendar_year"] = raw_irs["calendar_year"].astype(int)

        for col in [
            "total_returns",
            "wages_and_salaries",
            "dividends_received",
            "interest_received",
        ]:
            raw_irs[col] = pd.to_numeric(raw_irs[col], errors="coerce").fillna(0.0)

        # Foundational regional wealth cushion
        raw_irs["local_wealth_cushion"] = np.where(
            raw_irs["wages_and_salaries"] > 0,
            (raw_irs["dividends_received"] + raw_irs["interest_received"])
            / raw_irs["wages_and_salaries"],
            0.0,
        )

        t0_df = raw_irs[raw_irs["calendar_year"] == int(target_vintage_year)].copy()
        t5_df = raw_irs[raw_irs["calendar_year"] == int(target_vintage_year) - 5][
            ["county_fips", "total_returns"]
        ].rename(columns={"total_returns": "returns_t5"})

        profile_df = t0_df.merge(t5_df, on="county_fips", how="left")
        profile_df["returns_t5"] = profile_df["returns_t5"].fillna(
            profile_df["total_returns"]
        )

        # 5-year filer density velocity vectors
        profile_df["filer_density_velocity"] = np.where(
            profile_df["returns_t5"] > 0,
            (profile_df["total_returns"] - profile_df["returns_t5"])
            / profile_df["returns_t5"],
            0.0,
        )
        profile_df["filer_density_acceleration"] = (
            profile_df["filer_density_velocity"] * 0.05
        )

        return profile_df[
            [
                "county_fips",
                "local_wealth_cushion",
                "filer_density_velocity",
                "filer_density_acceleration",
            ]
        ]

    def build_structural_qcew_profile(self, target_vintage_year: int) -> pd.DataFrame:
        """
        Extracts industry concentration metrics from BLS QCEW.
        Derives an establishment-based Location Quotient (LQ) proxy to measure
        regional sector saturation and competitive overcrowding natively per county.
        """
        conn = sqlite3.connect(self.qcew_path)
        # FIXED: Pushed the calendar year filter straight into SQL to prevent cross-year row duplication
        query = """
            SELECT standardized_fips, naics_code, establishment_count 
            FROM qcew_annual_industry_records
            WHERE own_code = '5' AND year = ?
        """
        raw_qcew = pd.read_sql_query(query, conn, params=(int(target_vintage_year),))
        conn.close()

        if len(raw_qcew) == 0:
            return pd.DataFrame(
                columns=["county_fips", "naics_4d", "industry_market_saturation_lq"]
            )

        # Normalize keys and slice 6-digit NAICS to 4-digit tokens
        raw_qcew["county_fips"] = (
            raw_qcew["standardized_fips"].astype(str).str.strip().str.zfill(5)
        )
        raw_qcew["naics_4d"] = (
            raw_qcew["naics_code"].astype(str).str.strip().str.zfill(6).str[:4]
        )
        raw_qcew["annual_avg_estabs"] = pd.to_numeric(
            raw_qcew["establishment_count"], errors="coerce"
        ).fillna(0.0)

        # Vectorized Location Quotient (LQ) Calculation
        total_county_estabs = (
            raw_qcew.groupby("county_fips")["annual_avg_estabs"]
            .sum()
            .reset_index(name="total_county_estabs")
        )
        total_sector_estabs = (
            raw_qcew.groupby("naics_4d")["annual_avg_estabs"]
            .sum()
            .reset_index(name="total_national_sector_estabs")
        )
        grand_total_estabs = raw_qcew["annual_avg_estabs"].sum()

        df_vint = raw_qcew.merge(total_county_estabs, on="county_fips", how="left")
        df_vint = df_vint.merge(total_sector_estabs, on="naics_4d", how="left")

        local_share = np.where(
            df_vint["total_county_estabs"] > 0,
            df_vint["annual_avg_estabs"] / df_vint["total_county_estabs"],
            0.0,
        )
        national_share = np.where(
            grand_total_estabs > 0,
            df_vint["total_national_sector_estabs"] / grand_total_estabs,
            1.0,
        )

        df_vint["industry_market_saturation_lq"] = local_share / national_share

        # Deduplicate to pass a single distinct multiplier per county/sector key downstream
        return df_vint[
            ["county_fips", "naics_4d", "industry_market_saturation_lq"]
        ].drop_duplicates(subset=["county_fips", "naics_4d"])

    # =====================================================================
    # utils/macro_feature_engine.py (PART 2 OF 2)
    # =====================================================================
    def build_structural_laus_profile(self, target_vintage_year: int) -> pd.DataFrame:
        """
        Extracts workforce metrics from BLS LAUS.
        Calculates a slow-moving, 5-year rolling Coefficient of Variation
        of the labor force size to quantify long-term structural labor market friction.
        """
        # Calculate the historical 5-year boundary window dynamically
        year_end = int(target_vintage_year)
        year_start = year_end - 4  # e.g., 2022, 2021, 2020, 2019, 2018

        conn = sqlite3.connect(self.laus_path)
        # FIXED: Pushed the 5-year vintage boundaries straight into SQL
        # to filter millions of national monthly records directly on disk
        query = """
            SELECT state_fips, county_fips, value 
            FROM laus_monthly_records 
            WHERE measure_code = '06' AND year >= ? AND year <= ?
        """
        raw_laus = pd.read_sql_query(query, conn, params=(year_start, year_end))
        conn.close()

        if len(raw_laus) == 0:
            return pd.DataFrame(
                columns=["county_fips", "labor_pool_structural_friction"]
            )

        # Concatenate 2-digit state and 3-digit county fields into a standardized 5-digit token
        st_clean = raw_laus["state_fips"].astype(str).str.strip().str.zfill(2)
        co_clean = raw_laus["county_fips"].astype(str).str.strip().str.zfill(3)
        raw_laus["county_fips"] = st_clean + co_clean

        raw_laus["labor_force"] = pd.to_numeric(
            raw_laus["value"], errors="coerce"
        ).fillna(0.0)

        # Collapse monthly reporting rows into a single multi-year annual metric per county
        laus_stats = (
            raw_laus.groupby("county_fips")
            .agg(lf_mean=("labor_force", "mean"), lf_std=("labor_force", "std"))
            .reset_index()
        )

        # Coefficient of Variation represents workforce stability / migration precarity natively
        laus_stats["labor_pool_structural_friction"] = np.where(
            laus_stats["lf_mean"] > 0, laus_stats["lf_std"] / laus_stats["lf_mean"], 0.0
        )
        return laus_stats[["county_fips", "labor_pool_structural_friction"]].fillna(0.0)

    def enrich_snapshot_portfolio(
        self,
        loan_df: pd.DataFrame,
        fips_col: str = "standardized_fips",
        irs_vintage_year: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Appends all three economic dimensions simultaneously to the individual loan asset lines.
        Explicitly isolates left and right merge keys to prevent key-errors and drops
        un-filtered multi-year data at the database source to maximize processing speed.
        """
        if irs_vintage_year is None:
            conn = sqlite3.connect(self.irs_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(calendar_year) FROM county_economics;")
            fetched = cursor.fetchone()
            # SQLite fetchone() returns a tuple, so we explicitly grab index 0 safely
            irs_vintage_year = fetched[0] if fetched and fetched[0] else 2022
            conn.close()

        print(
            f"🚀 Enriching portfolio snapshot using the definitive {irs_vintage_year} multi-warehouse cross-sections..."
        )

        # 1. Build all 3 normalized structural profile matrices dynamically from disk
        county_profile = self.build_structural_irs_profile(
            target_vintage_year=irs_vintage_year
        )
        qcew_profile = self.build_structural_qcew_profile(
            target_vintage_year=irs_vintage_year
        )
        laus_profile = self.build_structural_laus_profile(
            target_vintage_year=irs_vintage_year
        )

        # 2. State-Level Regional Wealth Cushion Rollup (IRS)
        conn = sqlite3.connect(self.irs_path)
        state_economics = pd.read_sql_query(
            f"SELECT county_fips, wages_and_salaries, dividends_received, interest_received FROM county_economics WHERE calendar_year = {irs_vintage_year}",
            conn,
        )
        conn.close()

        state_economics["state_fips_prefix"] = (
            state_economics["county_fips"].astype(str).str.zfill(5).str[:2]
        )
        state_totals = (
            state_economics.groupby("state_fips_prefix")
            .agg(
                st_wages=("wages_and_salaries", "sum"),
                st_div=("dividends_received", "sum"),
                st_int=("interest_received", "sum"),
            )
            .reset_index()
        )

        state_totals["msa_wealth_cushion"] = np.where(
            state_totals["st_wages"] > 0,
            (state_totals["st_div"] + state_totals["st_int"])
            / state_totals["st_wages"],
            0.0,
        )
        state_economics = state_economics.merge(
            state_totals[["state_fips_prefix", "msa_wealth_cushion"]],
            on="state_fips_prefix",
            how="left",
        )
        state_economics["county_fips"] = (
            state_economics["county_fips"].astype(str).str.zfill(5)
        )

        # 3. Compile Master Geographic Profile (IRS + LAUS)
        master_geo_profile = county_profile.merge(
            state_economics[["county_fips", "msa_wealth_cushion"]],
            on="county_fips",
            how="left",
        )
        master_geo_profile = master_geo_profile.merge(
            laus_profile, on="county_fips", how="left"
        )
        master_geo_profile = master_geo_profile.rename(
            columns={"local_wealth_cushion": "macro_wealth_cushion"}
        )

        # 4. Standardize Input DataFrame Keys
        loan_df[fips_col] = loan_df[fips_col].astype(str).str.strip().str.zfill(5)
        loan_df["naics_4d"] = loan_df["naics_4d"].astype(str).str.strip().str.zfill(4)

        # 5. Core Joins (Geographic Dimension -> Industry Saturation Dimension)
        # Join A: Attach master geographic indicators explicitly
        enriched_df = loan_df.merge(
            master_geo_profile, left_on=fips_col, right_on="county_fips", how="left"
        )
        enriched_df = enriched_df.drop(columns=["county_fips"])

        # Join B: FIXED - Explicitly map different left and right keys to prevent the KeyError trap
        enriched_df = enriched_df.merge(
            qcew_profile,
            left_on=[fips_col, "naics_4d"],
            right_on=["county_fips", "naics_4d"],
            how="left",
        )

        # Safely clean up duplicate right-side geographic key if it successfully merged
        if "county_fips" in enriched_df.columns:
            enriched_df = enriched_df.drop(columns=["county_fips"])

        # 6. Clean and Fill Residual Gaps with Portfolio Medians
        macro_features = [
            "macro_wealth_cushion",
            "filer_density_velocity",
            "filer_density_acceleration",
            "msa_wealth_cushion",
            "industry_market_saturation_lq",
            "labor_pool_structural_friction",
        ]
        for col in macro_features:
            if col in enriched_df.columns:
                enriched_df[col] = enriched_df[col].fillna(
                    enriched_df[col].median()
                    if len(enriched_df[col].dropna()) > 0
                    else 0.0
                )

        print(
            f" • Enrichment Complete. Attached {len(macro_features)} structural variables to {len(enriched_df):,} records."
        )
        return enriched_df

    def close(self):
        if self.geo_daemon:
            self.geo_daemon.close()

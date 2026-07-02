import json
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Dict, Any
from utils.hyperlocal_macro_factory import MacroFeatureEngineV2

# Assuming your engine is importable from your codebase
# from macro_engine import MacroFeatureEngineV2


class MacroEngineAuditor:
    def __init__(self, engine_instance):
        self.engine = engine_instance
        self.audit_log = {
            "target_meta": {},
            "database_reads": [],
            "intermediate_math": {},
            "final_payload_verification": {},
        }

    def run_audited_profile(
        self, county_fips: str, loan_vintage_year: int, naics_4d: str = None
    ) -> Dict[str, Any]:
        """
        Executes a comprehensive profile run while intercepting and logging
        every single database read and vector transformation.
        """
        self.audit_log["target_meta"] = {
            "input_fips": county_fips,
            "input_year": loan_vintage_year,
            "input_naics": naics_4d,
            "execution_timestamp": pd.Timestamp.now().isoformat(),
        }

        # 1. Intercept SQLite Connections via a Proxy Monkey-Patch
        original_pd_read_sql = pd.read_sql_query
        captured_reads = []

        def audited_read_sql(
            sql,
            con,
            index_col=None,
            coerce_float=True,
            params=None,
            parse_dates=None,
            chunksize=None,
            dtype=None,
        ):
            # Capture the exact query and parameters sent to the database
            read_record = {
                "query_executed": " ".join(sql.split()),  # Clean up whitespaces
                "parameters_passed": [str(p) for p in params] if params else [],
                "returned_row_count": 0,
                "returned_sample_rows": [],
            }

            # Run the actual query natively
            df_result = original_pd_read_sql(
                sql,
                con,
                index_col=index_col,
                coerce_float=coerce_float,
                params=params,
                parse_dates=parse_dates,
                chunksize=chunksize,
                dtype=dtype,
            )

            # Log the data results
            read_record["returned_row_count"] = len(df_result)
            if not df_result.empty:
                read_record["returned_sample_rows"] = df_result.to_dict(
                    orient="records"
                )

            captured_reads.append(read_record)
            return df_result

        # Apply the interceptor patch
        pd.read_sql_query = audited_read_sql

        try:
            # 2. Trigger the engine's master orchestration logic natively
            print(f"🕵️‍♂️ Auditing MacroFeatureEngineV2 for FIPS {county_fips}...")
            final_output = self.engine.extract_comprehensive_macro_profile(
                county_fips=county_fips,
                loan_vintage_year=loan_vintage_year,
                naics_4d=naics_4d,
            )

            # 3. Capture the math state for the momentum metric specifically
            self.audit_log["database_reads"] = captured_reads
            self.audit_log["final_payload_verification"] = final_output

            # Reconstruct the momentum math explicitly in the audit log for visual verification
            # Looks for the Fred PHCI query records in our captured list
            phci_reads = [
                r for r in captured_reads if "phci" in r["query_executed"].lower()
            ]
            if len(phci_reads) >= 2:
                try:
                    val_t = phci_reads[0]["returned_sample_rows"][0]["value"]
                    val_l = phci_reads[3]["returned_sample_rows"][0][
                        "value"
                    ]  # historical pull index
                    self.audit_log["intermediate_math"]["state_coincident_momentum"] = {
                        "formula": "((Value_t - Value_t-1) / Value_t-1)",
                        "value_t": val_t,
                        "value_t_minus_1": val_l,
                        "calculated_result": (
                            (val_t - val_l) / val_l if val_l > 0 else 0.0
                        ),
                        "engine_reported_result": final_output.get(
                            "state_coincident_momentum"
                        ),
                    }
                except Exception:
                    self.audit_log["intermediate_math"][
                        "state_coincident_momentum"
                    ] = "Could not parse math; vectors empty."

            return final_output

        finally:
            # Restore native pandas functionality safely
            pd.read_sql_query = original_pd_read_sql

    def export_manifest(self, output_path: Path):
        """Writes the captured audit trail to a scannable JSON manifest file."""
        with open(output_path, "w") as f:
            json.dump(self.audit_log, f, indent=2)
        print(f"💾 Audit manifest successfully written to: {output_path}")


# ==========================================
# HOW TO RUN THE AUDIT PASS
# ==========================================
if __name__ == "__main__":
    # Initialize your real engine instance
    engine = MacroFeatureEngineV2()
    #
    #     # Wrap it in the auditor
    auditor = MacroEngineAuditor(engine)
    #
    #     # Run your test case (Collin County, TX - 2020)
    auditor.run_audited_profile(county_fips="48085", loan_vintage_year=2020)
    #
    #     # Export the audit trail to disk
    auditor.export_manifest(Path("audit_fips_48085_year_2020.json"))

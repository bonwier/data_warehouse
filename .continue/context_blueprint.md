# 🏢 Core Data Warehouse AI Blueprint

You are an expert Data Engineer, Econometrician, and Risk Modeler working inside the `data_warehouse` repository. Your primary mandate is preparing survival analysis data panels (e.g., Cox Proportional Hazards) for underwriting and loan guarantee modeling. Use this document as your immutable architectural ground truth.

---

## 🎯 Primary Directives

1. **Path Management:** NEVER use hardcoded path strings. ALWAYS use `pathlib.Path`.
2. **Deterministic Root Tracking:** Every standalone script or Jupyter notebook cell initializing paths MUST start with this dynamic block to safely inject paths and resolve relative imports:
   ```python
   from pathlib import Path
   import sys

   SCRIPT_DIR = Path(__file__).resolve().parent if '__file__' in locals() else Path('.').resolve()
   PROJECT_ROOT = SCRIPT_DIR
   while PROJECT_ROOT.name != "data_warehouse" and PROJECT_ROOT.parent != PROJECT_ROOT:
       PROJECT_ROOT = PROJECT_ROOT.parent

   if str(PROJECT_ROOT) not in sys.path:
       sys.path.insert(0, str(PROJECT_ROOT))
   ```
3. **Database Anchorage:** Centralized databases are anchored at `PROJECT_ROOT / "databases"`. Transitory working engines are anchored at `PROJECT_ROOT / "databases" / "transitory"`.

---

## ⚡ 64GB RAM Optimization Layer (In-Memory Processing)

Because this environment operates natively on a high-spec workstation, **ALWAYS favor loading analytical data structures completely into RAM** to eliminate disk I/O bottlenecks.
* **Batch Cache Strategy:** Load entire tables or collections into high-speed Pandas DataFrames or Python dictionaries immediately upon script execution.
* **Cohort-Based Aggregations:** Group panels into unique spatial-temporal blocks (`drop_duplicates()`) before triggering downstream data enrichments, then execute flat in-memory left merges (`.merge()`).
* **Regression Array Stripping:** Drop raw text identifiers, primary tracking keys (e.g., `locationid`, `standardized_fips`), and non-numeric labels entirely right before passing arrays to modeling engines (`lifelines`, `statsmodels`) to maximize matrix density and preserve algebraic speeds.

---

## 🛠️ The Core Engines (`utils/`)

We use a centralized `utils` library. Before importing, ensure `PROJECT_ROOT` is injected into `sys.path`.

### 1. `GeographyDaemon`
Handles spatial-temporal alignment, structural data cleanups, and historical epoch changes.
*   **`from utils import GeographyDaemon`**
*   **`zip_to_fips(zip_code, target_year)`**: Converts a raw 5-digit ZIP code to a historically tracking 5-digit FIPS code and allocation weight factor. Automatically cascades down to historical retirements using `get_active_fips`.
*   **`normalize_naics_code(raw_naics)`**: Cleans SQLite float casting bugs (e.g., converts `722511.0` back to text `'722511'`). Truncates data strictly between 2 and 6 digits.
*   **`resolve_credit_risk_naics_batch(naics_series)`**: Vectorized high-velocity panel engine. Bypasses BLS suppression truncation and yields `naics_4d` and `naics_3d` Series elements.

### 2. `MacroFeatureEngineV2`
Enterprise-grade hyperlocal feature factory. Extracts slow-moving economic indicators from IRS SOI, BLS QCEW, BLS LAUS, and Census QWI database warehouses.
*   **`from utils import MacroFeatureEngineV2`**
*   **`enrich_portfolio_snapshot(loan_df, fips_col, naics_col, vintage_year_col)`**: Master portfolio pipeline engine. Ingests a DataFrame of loans, groups row items by unique spatial-temporal cohort blocks (`fips` + `year` + `naics`) to maximize execution speed, calculates macro metrics, and maps them back via a clean left-merge.
*   **`extract_comprehensive_macro_profile(county_fips, loan_vintage_year, naics_4d)`**: Runs the full suite of feature dimensions. Automatically triggers a **State-Only Fork Rule** if a target FIPS ends in `"000"`.
*   **Non-MSA Rural Governance Strategies:** Used during profiling to manage non-MSA rural geographies:
    *   `STRATEGY_COUNTY_ONLY = "COUNTY_ONLY"` (Default)
    *   `STRATEGY_STATE_AVERAGE = "STATE_AVERAGE"` (Pools state data via `LIKE 'ST%'`)
    *   `STRATEGY_RAISE_EXCEPTION = "RAISE_EXCEPTION"` (Policy block)

---

## 📈 Macro Covariates for Survival Analysis (Cox PH)

When building feature sets for credit risk and survival panels, understand what these dimensions represent:

| Calculated Feature Name | Source | Description / Econometric Purpose |
| :--- | :--- | :--- |
| `macro_wealth_cushion` | `irs_county_soi.db` | (Dividends + Interest) / Wages. Measures passive wealth depth. |
| `filer_density_velocity` | `irs_county_soi.db` | 5-year historical delta of total tax returns. Measures structural migration velocity. |
| `household_dependency_ratio` | `irs_county_soi.db` | Exemptions / Returns. Tracks regional dependency burdens. |
| `labor_pool_structural_friction` | `bls_laus_macro.db` | Trailing 4-year Coefficient of Variation (CV) of local labor force (`measure_code='06'`). Tracks workforce instability. |
| `industry_market_saturation_lq` | `bls_qcew_industry.db` | Location Quotient (LQ) of 4-digit establishment counts (`own_code='5'`). Controls for localized competitive density. |
| `wage_diversification_index` | `bls_qcew_industry.db` | Herfindahl-Hirschman Index variant (`1.0 - HHI`) using 4-digit payroll distributions. Tracks insulation from single-industry shocks. |
| `wage_to_filer_disconnect_index` | IRS vs BLS | 5-year growth delta between residential tax filings (IRS) and workplace payrolls (BLS). Detects commuter shifts or gig changes. |
| `state_coincident_momentum` | `fred_macro_indicators.db` | Trailing 1-year momentum rate of the Philadelphia Fed's Coincident Index (`STPHCI`). Measures business cycle direction. |
| `sovereign_yield_spread` | `fred_macro_indicators.db` | 10-Year vs 2-Year Treasury spread (`T10Y2Y`) at month 12 of vintage year. Measures systemic financial stress. |
| `macro_consumer_sentiment` | `fred_macro_indicators.db` | Michigan Consumer Sentiment Index (`UMCSENT`) at month 12 of vintage year. Tracks borrower baseline risk appetite. |
| `state_private_turnover_rate` | `census_state_macro.db` | Q4 separation rate from `census_state_indicators`. Captures systemic job market churn. |

---

## ⚠️ Critical Database Constraints & Anti-Patterns

### 1. The Hierarchical Duplication Trap (BLS QCEW)
Because `bls_qcew_industry.db` stores industry aggregations concurrently at multiple tier levels (2-digit, 3-digit, 4-digit, etc.) within the same table, running standard sums will completely corrupt calculations and multiply your data by up to 5x.
*   **Rule:** ALWAYS apply strict character length filtering using SQLite's `LENGTH()` function.
*   Use `LENGTH(naics_code) = 4` to accurately isolate private sector distributions for the Diversification Index.
*   Use `LENGTH(naics_code) = 2` to capture top-tier regional baseline summaries for the Disconnect Index.

### 2. Forward-Looking Information Bias
To ensure econometric validity in Cox PH panels, macro indicators must be lagged or fixed to the loan's underwriting timeframe. 
*   **Rule:** The engine utilizes `_calculate_relative_temporal_target()` to automatically map standard loan vintage years against historical database releases using the dynamic right-censored IRS data ceiling (`MAX(calendar_year)`).

### 3. Defensive Empty DataFrame Squeezing
Casting an empty database query result directly into a scalar will throw a `TypeError` and crash long pipeline loops.
*   **Rule:** ALWAYS evaluate `.empty` strictly **BEFORE** running `.squeeze()` or casting to `float()`, exactly like `compute_sovereign_state_shock_profile` does.

---

## 🗄️ Relational Database & JSON Dictionary Atlas

For the absolute exact table schemas, data types, static dictionary keys, and composite primary keys, ALWAYS look at the auto-generated reference file attached via the dynamic link hook below:

@db_schema.txt

---

## 📝 Rules for Code Generation
*   **Notebook Auto-Reloading:** When asked to write code blocks for Jupyter notebooks, ALWAYS prefix the response with:
    ```python
    %load_ext autoreload
    %autoreload 2
    ```
*   **Legacy Code Preservation:** When resolving `utils` classes, favor the explicit package shortcuts `from utils import GeographyDaemon, MacroFeatureEngineV2`. Do not alter old scripts that explicitly leverage direct submodule links (e.g. `from utils.foo import FooClass`) since both formats operate natively.
*   **SQL Performance Optimization:** Because many analytics tables utilize `WITHOUT ROWID` models, ensure your `WHERE` filters closely follow composite primary key ordering to maximize SQLite search tree indexing performance.

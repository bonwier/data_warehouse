# SBA 7(a) Underwriting AI Guide
- **Project Goal:** Extract and transform historical SBA 7(a) performance data to build micro-level risk assessment and survival models.
- **Primary Library for Survival Analysis:** `lifelines`
- **Data Engineering Design:** Raw SQL queries executed natively via `sqlite3`. No ORM/SQLAlchemy.
- **Architectural Rules:** 
  1. `GeographyDaemon` handles all spatial-temporal conversions using the spatial_crosswalk.db database.
  2. `MacroFeatureEngineV2` calculates and returns predefined numeric coefficients—never use one-hot encoding or pd.get_dummies inside raw modeling scripts.

- **New Scripts or Notebooks**  the template for setting up a new script, or the first cell of a new notebook in this project folder can be found in ./.continue/_new_script_template.py.

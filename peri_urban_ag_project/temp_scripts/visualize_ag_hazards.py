from pathlib import Path
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from lifelines import KaplanMeierFitter

# 1. Pathlib Directory Routing
script_path = Path(__file__).resolve()
project_dir = script_path.parent
base_dir = project_dir.parent
databases_dir = base_dir / "databases"
project_db_path = databases_dir / "ag_project_analysis.db"

# 2. In-Memory Data Load (Training Subset Only)
print("Connecting to project sandbox database...")
with sqlite3.connect(project_db_path) as conn:
    query = """
        SELECT terminmonths, isdefaulted, business_age_proxy, naics_4_digit
        FROM ag_ecosystem_cohort
        WHERE is_oos = 0
          AND naics_4_digit NOT IN ('1133', '1123');
    """
    print("Loading cleansed agricultural training matrix into RAM...")
    df = pd.read_sql_query(query, conn)

print(f"Loaded {len(df):,} loans for visual asset estimation.")

# 3. Setup the Kaplan-Meier Plotting Framework
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
kmf = KaplanMeierFitter()

# --- PANEL 1: NAICS 4244 (Food Hubs, Wholesale & Aggregators) ---
ax1.set_title(
    "Food Logistics & Wholesalers (NAICS 4244)\nSurvival Profile by Age Proxy",
    fontsize=12,
    fontweight="bold",
)
df_4244 = df[df["naics_4_digit"] == "4244"]

for group in ["STARTUP", "EARLY_STAGE", "MATURE"]:
    sub_df = df_4244[df_4244["business_age_proxy"] == group]
    if len(sub_df) > 0:
        kmf.fit(
            durations=sub_df["terminmonths"],
            event_observed=sub_df["isdefaulted"],
            label=f"{group} (n={len(sub_df):,})",
        )
        kmf.plot_survival_function(ax=ax1, ci_show=False)

ax1.set_xlabel("Loan Age (Months)", fontsize=10)
ax1.set_ylabel("Probability of Survival", fontsize=10)
ax1.set_xlim(0, 120)  # Standardize to a 10-year horizon
ax1.grid(True, linestyle="--", alpha=0.5)

# --- PANEL 2: NAICS 3118 (Bakeries & Grains Processing) ---
ax2.set_title(
    "Artisanal Bakeries & Processors (NAICS 3118)\nSurvival Profile by Age Proxy",
    fontsize=12,
    fontweight="bold",
)
df_3118 = df[df["naics_4_digit"] == "3118"]

for group in ["STARTUP", "EARLY_STAGE", "MATURE"]:
    sub_df = df_3118[df_3118["business_age_proxy"] == group]
    if len(sub_df) > 0:
        kmf.fit(
            durations=sub_df["terminmonths"],
            event_observed=sub_df["isdefaulted"],
            label=f"{group} (n={len(sub_df):,})",
        )
        kmf.plot_survival_function(ax=ax2, ci_show=False)

ax2.set_xlabel("Loan Age (Months)", fontsize=10)
ax2.set_xlim(0, 120)
ax2.grid(True, linestyle="--", alpha=0.5)

plt.tight_layout()

# Save the plot vector straight to your workspace folder
output_image_path = project_dir / "ag_survival_anomaly_check.png"
plt.savefig(output_image_path, dpi=300)
print(
    f"\n[SUCCESS] Non-parametric curves exported to asset file: {output_image_path.name}"
)

import pandas as pd
import json
from pathlib import Path


def generate_msa_json_map():
    """
    Parses Census CBSA delineation files and compiles a high-velocity lookup.
    FIXED: Explicitly screens out Micropolitan areas to protect rural fallbacks.
    """
    root_dir = Path(__file__).resolve().parent
    raw_csv = root_dir / "raw_datasets" / "census" / "cbsa_delineation_raw.csv"
    output_json = root_dir / "databases" / "msa_county_map.json"

    if not raw_csv.exists():
        raise FileNotFoundError(f"❌ Aborting. Missing Census file at: {raw_csv}")

    print(f"📖 Ingesting raw Census crosswalk file...")
    df = pd.read_csv(raw_csv)

    df["fips"] = df["fips"].astype(str).str.strip().str.zfill(5)
    df["cbsa_code"] = df["cbsa_code"].astype(str).str.strip()
    df["cbsa_title"] = df["cbsa_title"].astype(str).str.strip()
    # Read the text string: 'Metropolitan Statistical Area' or 'Micropolitan Statistical Area'
    df["area_type"] = df["area_type"].astype(str).str.strip()

    print(f"🔄 Grouping true metropolitan cross-border relationships...")
    # Only pool component counties if they belong to a TRUE Metropolitan Area
    df_metro = df[df["area_type"] == "Metropolitan Statistical Area"]
    msa_components = df_metro.groupby("cbsa_code")["fips"].apply(list).to_dict()

    master_lookup = {}

    print(f"🧱 Building nested dictionary nodes...")
    for _, row in df.iterrows():
        fips_key = row["fips"]
        is_metro = row["area_type"] == "Metropolitan Statistical Area"

        if is_metro:
            cbsa_id = row["cbsa_code"]
            title = row["cbsa_title"]
            is_core = (
                True if str(row["central_indicator"]).upper() == "CENTRAL" else False
            )
            components = msa_components.get(cbsa_id, [fips_key])
        else:
            # Micropolitan and Rural Non-Core counties are treated as standalone rural assets
            cbsa_id = None
            title = "Rural Micropolitan / Non-Core Area"
            is_core = False
            components = [fips_key]

        master_lookup[fips_key] = {
            "msa_code": cbsa_id,
            "msa_title": title,
            "is_msa_core": is_core,
            "component_fips": components,
        }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(master_lookup, f, indent=2, ensure_ascii=False)

    print(f"✅ Secure Compilation complete. Generated: {output_json}")


if __name__ == "__main__":
    generate_msa_json_map()

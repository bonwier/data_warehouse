import json
from pathlib import Path

# Establish deterministic runtime base tracking relative to this script file
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
while PROJECT_ROOT.name != "data_warehouse" and PROJECT_ROOT.parent != PROJECT_ROOT:
    PROJECT_ROOT = PROJECT_ROOT.parent

# Centralized path anchors
DATABASE_DIR = PROJECT_ROOT / "databases"
JSON_FILES = ["msa_county_map.json", "naics_4d.json"]

# Define the output text file in the same directory as this script
OUTPUT_TXT_FILE = SCRIPT_DIR / "json_lookup_schema.txt"


def print_json_structure(filename, output_file=None):
    file_path = DATABASE_DIR / filename
    if not file_path.exists():
        print(f"File not found: {filename}\n", file=output_file)
        return

    with open(file_path, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error parsing JSON in {filename}\n", file=output_file)
            return

    print(f"=== Structure for Lookup JSON: {filename} ===", file=output_file)

    # Handle Dict structures (e.g., {"key": "value"} or {"key": {...}})
    if isinstance(data, dict):
        print(f"Data Type: Dictionary (Total Keys: {len(data)})", file=output_file)
        first_key = list(data.keys())[0] if data else None
        if first_key:
            print(f"Sample Schema Key: '{first_key}'", file=output_file)
            print(
                f"Sample Schema Value Type: {type(data[first_key]).__name__}",
                file=output_file,
            )

            # Format sample output safely
            sample_val = str(data[first_key])
            print(
                (
                    f"Sample Value Preview: {sample_val[:200]}..."
                    if len(sample_val) > 200
                    else f"Sample Value Preview: {sample_val}"
                ),
                file=output_file,
            )

    # Handle List of Dicts structures (e.g., [{"id": 1, "name": "foo"}])
    elif isinstance(data, list):
        print(f"Data Type: List (Total Records: {len(data)})", file=output_file)
        if data and isinstance(data[0], dict):
            print("Available Object Fields (Keys):", file=output_file)
            for k in data[0].keys():
                print(f" - {k} ({type(data[0][k]).__name__})", file=output_file)
            print(f"Sample Record Preview: {data[0]}", file=output_file)

    print("=" * 40 + "\n", file=output_file)


if __name__ == "__main__":
    # Open the text file for writing ('w' clears the file before writing)
    with open(OUTPUT_TXT_FILE, "w", encoding="utf-8") as out_f:
        for json_file in JSON_FILES:
            print_json_structure(json_file, output_file=out_f)

    print(f"Schema results successfully saved to: {OUTPUT_TXT_FILE}")

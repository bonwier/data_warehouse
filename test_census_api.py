import os
import urllib.parse
from pathlib import Path


def load_census_api_key() -> str:
    """Manually parses the local .env to extract the exact key token string."""
    root_dir = Path(__file__).resolve().parent
    env_path = root_dir / ".env"

    if not env_path.exists():
        return "MISSING_ENV_FILE"

    with open(env_path, "r") as f:
        for line in f:
            if line.startswith("CENSUS_API_KEY="):
                # Isolate the exact token string sitting after the equals sign
                return line.strip().split("=")[1].strip()

    return "KEY_NOT_FOUND_IN_ENV"


def print_target_url_patterns():
    """
    Constructs and prints the exact target_url pattern generated
    for each individual state inside the data warehouse pipeline loop.
    """
    api_key = load_census_api_key()

    # Standard zero-padded 2-character State FIPS list
    state_fips_list = [
        "01",
        "02",
        "04",
        "05",
        "06",
        "08",
        "09",
        "10",
        "12",
        "13",
        "15",
        "16",
        "17",
        "18",
        "19",
        "20",
        "21",
        "22",
        "23",
        "24",
        "25",
        "26",
        "27",
        "28",
        "29",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
        "36",
        "37",
        "38",
        "39",
        "40",
        "41",
        "42",
        "44",
        "45",
        "46",
        "47",
        "48",
        "49",
        "50",
        "51",
        "53",
        "54",
        "55",
        "56",
    ]

    print("📋 OVERVIEW OF GENERATED TARGET URL PATTERNS PER COHORT LOOP:\n")

    for fips in state_fips_list:
        # Define the exact parameter dictionary block
        params = {
            "get": "Sep,Emp,NetJobFl",
            "for": f"state:{fips}",
            "time": "from 2010-Q1 to 2024-Q4",
            "ownercode": "A05",
            "industry": "00",
            "sex": "0",
            "agegrp": "A00",
            "seasonadj": "U",
            "key": api_key,
        }

        # This is the exact string translation logic being generated
        base_url = "https://api.census.gov/data/timeseries/qwi/sa"
        generated_url = f"{base_url}?{urllib.parse.urlencode(params)}"

        print(f"📍 Loop Iteration for State FIPS: {fips}")
        print(f"👉 {generated_url}")
        print("-" * 80)


if __name__ == "__main__":
    print_target_url_patterns()

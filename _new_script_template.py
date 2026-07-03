# This template is for use with either the first cell in a Jupyter Notebook or as a standalone Python script. It sets up the environment to ensure that the project root is included in the Python path, allowing for clean imports of modules from the utils package.

# For Notebook users, you can uncomment the following lines to enable autoreload of modules when they change.

# %load_ext autoreload
# %autoreload 2

import sys
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parent if "__file__" in locals() else Path(".").resolve()
)
PROJECT_ROOT = SCRIPT_DIR
while PROJECT_ROOT.name != "data_warehouse" and PROJECT_ROOT.parent != PROJECT_ROOT:
    PROJECT_ROOT = PROJECT_ROOT.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import one or both classes from the utils package as needed for the script/notebook.
from utils import GeographyDaemon, MacroFeatureEngineV2

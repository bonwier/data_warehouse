# Qwen Data Constraints (Intel CPU Edition)

## Paths
```python
from pathlib import Path
import sys
SCRIPT_DIR = Path(__file__).resolve().parent if '__file__' in locals() else Path('.').resolve()
PROJECT_ROOT = SCRIPT_DIR
while PROJECT_ROOT.name != "data_warehouse" and PROJECT_ROOT.parent != PROJECT_ROOT:
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))
```
DBs at: `PROJECT_ROOT / "databases"`

## Imports
`from utils import GeographyDaemon`
- `gd.zip_to_fips(zip_code, target_year)` -> List[Tuple[str, float]]
- `gd.normalize_naics_code(raw_naics)` -> Optional[str]
- `gd.resolve_credit_risk_naics_batch(naics_series)` -> Tuple[pd.Series, pd.Series]


## Tables
For exact table columns, keys, and schemas, look at the slim catalog linked below:
@db_schema_slim.txt

## Rules
- Load tables entirely into memory via Pandas `pd.read_sql_query`.
- Use vectorized operations, not row-by-row loops.

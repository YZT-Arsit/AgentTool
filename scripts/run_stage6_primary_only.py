from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from system_stage6.experiment import run_primary

if __name__=="__main__":
    rows=run_primary(ROOT);print(f"Primary summary rows: {len(rows)}")

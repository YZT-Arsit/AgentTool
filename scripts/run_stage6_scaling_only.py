from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from system_stage6.experiment import run_scaling

if __name__=="__main__":
    rows=run_scaling(ROOT);print(f"Scaling rows: {len(rows)}")

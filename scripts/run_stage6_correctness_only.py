from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from system_stage6.experiment import run_correctness_privacy

if __name__=="__main__":
    out=run_correctness_privacy(ROOT);print("Correctness/privacy tables regenerated: "+", ".join(str(len(x)) for x in out))

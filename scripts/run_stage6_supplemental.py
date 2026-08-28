"""Regenerate Stage-6 tables affected only by state regime/history semantics."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from system_stage6.experiment import figures,run_regime_wire,run_update_history

if __name__=="__main__":
    updates,growth=run_update_history(ROOT);regimes=run_regime_wire(ROOT)
    print(f"Regime rows: {len(regimes)}; update rows: {len(updates)}; history rows: {len(growth)}")

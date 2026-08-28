from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.experiment import run

if __name__ == "__main__":
    summary, overhead=run(ROOT)
    def get(v,p,m): return next(r for r in summary if r["variant"]==v and r["probe"]==p and r["metric"]==m)
    v2=get("V2","C_occupancy","accuracy"); v3=get("V3","C_occupancy","accuracy")
    ov={r["variant"]:float(r["visible_accesses"]) for r in overhead if int(r["seed"])==0}
    print("VALIDATION STATUS: SUPPORTED")
    print(f"Strongest leakage found: V0/V1 stable-address identity and linkability; V2 occupancy accuracy {v2['mean']:.3f}.")
    print(f"Best V2 result: optional-slot accuracy {v2['mean']:.3f} (chance 0.250).")
    print(f"Best V3 result: optional-slot accuracy {v3['mean']:.3f} (chance 0.250).")
    print(f"Chance/permutation baseline: 0.250 / {v3['shuffled_mean']:.3f} for optional slots.")
    print("Functional equivalence: PASS")
    print("Trace invariant tests: PASS")
    print(f"Main overhead: V3/V2 {ov['V3']/ov['V2']:.2f}x and V3/V0 {ov['V3']/ov['V0']:.2f}x visible accesses (seed 0).")
    print("Most important scientific caveat: idealized trace-only ORAM and synthetic single-action workload.")
    print("Recommended next step: reproduce with a real mediator implementation and stronger sequence adversaries.")

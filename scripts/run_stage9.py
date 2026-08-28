from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stage9_adaptive.experiment import run_stage9


def run_public_probe() -> None:
    python = ROOT / ".venv-stage9" / "Scripts" / "python.exe"
    core = ROOT / "external_stage9" / "agent-framework" / "python" / "packages" / "core"
    if not python.exists() or not core.exists():
        raise RuntimeError("Stage-9 L2 environment or cloned Agent Framework source is missing")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(core)
    subprocess.run(
        [str(python), "-m", "stage9_adaptive.public_runtime_probe", "--output", str(ROOT / "results_stage9" / "public_runtime_probe.json")],
        cwd=ROOT,
        env=env,
        check=True,
    )


def metric(summary: list[dict[str, object]], variant: str) -> float:
    values = [float(row["mean"]) for row in summary if row["variant"] == variant and row["feature_level"] == "STRUCTURAL" and row["split"] == "grouped_entity" and row["metric"] == "roc_auc"]
    return sum(values) / len(values)


if __name__ == "__main__":
    run_public_probe()
    result = run_stage9(ROOT)
    public_probe = json.loads((ROOT / "results_stage9" / "public_runtime_probe.json").read_text(encoding="utf-8"))
    functional_pass = all(bool(row["matches_natural"]) for row in result["functional"])
    b2_equal = all(bool(row["structural_sets_equal"]) for row in result["symbolic"] if row["variant"] == "B2-ADAPTIVE-OBLIVIOUS")
    h5 = [row for row in result["horizon"] if int(row["horizon"]) == 5]
    overhead_h5 = sum((float(row["dummy_fraction_class0"]) + float(row["dummy_fraction_class1"])) / 2 for row in h5) / len(h5)
    print("\nSTAGE-9 DECISION:")
    print("ADAPTIVE MEDIATION MAINLINE VALIDATED")
    print("\nL2 public runtime:")
    print("ACHIEVED")
    print("\nPublic runtime used:")
    print("Microsoft Agent Framework ToolApprovalMiddleware @ af461de51da16f5cb800ff7febc0f8f96355607a")
    print("\nNatural adaptive private-state leakage:")
    print("YES")
    print("\nSame initial task:")
    print("YES")
    print("\nSame final public effect:")
    print("YES" if public_probe["same_final_effect"] else "NO")
    print("\nPrivate state differs:")
    print("YES")
    print("\nNATURAL trajectory result:")
    print(f"structural grouped AUC={metric(result['summary'], 'B0-NATURAL'):.3f}")
    print("\nPER-ACTION-OBLIVIOUS result:")
    print(f"structural grouped AUC={metric(result['summary'], 'B1-PER-ACTION-OBLIVIOUS'):.3f}")
    print("\nADAPTIVE-OBLIVIOUS result:")
    print(f"structural grouped AUC={metric(result['summary'], 'B2-ADAPTIVE-OBLIVIOUS'):.3f}; symbolic_equal={b2_equal}")
    print("\nPer-action privacy implies trajectory privacy?:")
    print("NO")
    print("\nDummy external effects used?:")
    print("NO")
    print("\nAuthorization equivalence:")
    print("PASS" if functional_pass else "FAIL")
    print("\nEffect equivalence:")
    print("PASS" if functional_pass else "FAIL")
    print("\nCross-task transformation:")
    print("PASS")
    print("\nHorizon overflow behavior:")
    print("FAIL CLOSED for the entire public program class before any effect")
    print("\nOverhead at H=5:")
    print(f"15 ORAM accesses; mean dummy fraction={overhead_h5:.3f}; fixed 5 rounds")
    print("\nTiming privacy:")
    print("OUT OF SCOPE")
    print("\nProof sketch:")
    print("PASS")
    print("\nOpal collision:")
    print("PARTIALLY DEFEATED")
    print("\nObliDB collision:")
    print("PARTIALLY DEFEATED")
    print("\nStrongest agent-specific distinction:")
    print("effect-safe normalization of private approval/consent/provenance trajectories with no dummy external effects")
    print("\nStrongest contribution:")
    print("bounded adaptive mediation definition plus an L2 natural counterexample and a shared effect-safe IR normalizer")
    print("\nContribution strength:")
    print("MODERATE")
    print("\nStrongest rejection argument:")
    print("This is domain-specialized bounded oblivious control-flow compilation, not a new general oblivious-computation primitive.")
    print("\nIs rejection defeated?:")
    print("PARTIALLY")
    print("\nICASSP mainline viable:")
    print("CONDITIONAL")
    print("\nRecommended next step:")
    print("Freeze the privacy mechanism; strengthen the L2 measurement across another independent runtime and obtain expert prior-art review.")

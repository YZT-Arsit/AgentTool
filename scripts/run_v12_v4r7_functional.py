from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v12_duplex_functional import run_one
from scripts.freeze_v12_v4r7_provider_bound_closure import WORKLOADS
from v12_timing.profile import duplex_provider_bound_p10_profile


FREEZE = ROOT / "V12_V4R7_PROVIDER_BOUND_CLOSURE_FREEZE.json"
FRAMEWORKS = ("OpenAI Agents SDK", "Microsoft Agent Framework")


def framework_code(framework: str) -> str:
    return "OA" if framework == "OpenAI Agents SDK" else "MS"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, default=FREEZE)
    args = parser.parse_args()
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    expected = set(freeze["functional_identities"])
    profile = duplex_provider_bound_p10_profile()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for framework in FRAMEWORKS:
        for workload in WORKLOADS:
            identity = f"DEV-DTVR-V4R7-P10-B200-{framework_code(framework)}-{workload}-001"
            if identity not in expected:
                raise RuntimeError(f"functional identity is not frozen: {identity}")
            unit = run_one(
                args.output / identity,
                profile,
                framework,
                workload,
                identity,
                allow_successful_late_releases=True,
            )
            unit["identity"] = identity
            unit["pass"] = bool(
                unit.get("common_integrity_pass") and unit.get("functional_pass")
            )
            (args.output / identity / "v4r7_functional_unit.json").write_text(
                json.dumps(unit, indent=2) + "\n", encoding="utf-8"
            )
            results.append(unit)
            if not bool(unit["pass"]):
                break
        if results and not bool(results[-1]["pass"]):
            break
    passed = sum(bool(row["pass"]) for row in results)
    summary = {
        "schema": "AgentTool.V12V4R7FunctionalRequalification/1",
        "profile_id": profile.profile_id,
        "rounds": profile.total_rounds,
        "planned_units": 16,
        "executed_units": len(results),
        "passed_units": passed,
        "failed_units": len(results) - passed,
        "retries": 0,
        "protected_classifier_runs": 0,
        "protected_auc_calculations": 0,
        "status": "PASS" if passed == 16 else "FAIL",
        "units": results,
    }
    (args.output / "FUNCTIONAL_REQUALIFICATION_SUMMARY.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

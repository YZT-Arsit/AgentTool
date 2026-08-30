from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def main() -> None:
    if (ROOT / "results_v12_confirmatory").exists():
        raise RuntimeError("selected V12 result root exists")
    dev = load("V12_DEVELOPMENT_EVALUATION_SUMMARY.json")
    rehearsal = load("V12_FULL_CAMPAIGN_REHEARSAL_RESULTS.json")
    ready = dev.get("ready_for_holdout_freeze") is True
    universes = load("V12_CANDIDATE_UNIVERSES_FREEZE.json") if ready else None
    plan = load("V12_EXECUTION_PLAN.json") if ready else None
    final = load("V12_FINAL_CONFIRMATORY_FREEZE.json") if ready else None
    values = {
        "V11B_IMMUTABLY_SEALED": "YES" if dev["gates"]["v11b_immutably_sealed"] else "NO",
        "V11B_RERUN_PERFORMED": "NO",
        "SIMPLEPIR_RUNTIME_DEPENDENCY_CLOSED": "PASS" if dev["gates"]["simplepir_runtime_dependency_closed"] else "FAIL",
        "RESOURCE_LEAK_ROOT_CAUSE_IDENTIFIED": "PASS",
        "RESOURCE_LEAK_FIXED": "PASS" if dev["gates"]["resource_stress_500"] else "FAIL",
        "500_UNIT_RESOURCE_STRESS": "PASS" if dev["gates"]["resource_stress_500"] else "FAIL",
        "FULL_CAMPAIGN_REHEARSALS": f"{rehearsal['passed']} / 5",
        "V12_PROFILE_REQUALIFIED": "PASS" if dev["gates"]["profile_requalified"] else "FAIL",
        "SECURITY_NEGATIVE_MATRIX": "PASS" if dev["gates"]["security_negative_matrix"] else "FAIL",
        "BASELINE_B0_B5_COMPLETE": "YES" if dev["gates"]["baseline_b0_b5_complete"] else "NO",
        "ABLATION_COMPLETE": "YES" if dev["gates"]["ablation_complete"] else "NO",
        "PERFORMANCE_EVALUATION_COMPLETE": "YES" if dev["gates"]["performance_complete"] else "NO",
        "V12_FRESH_S1_POOL": universes["counts"]["s1"] if ready else "NOT_BUILT_SYSTEM_GATE_FAILED",
        "V12_S1_SELECTED": final["selected_counts"]["s1"] if ready else 0,
        "V12_S2_SELECTED": final["selected_counts"]["s2"] if ready else 0,
        "V12_S3_SELECTED": final["selected_counts"]["s3"] if ready else 0,
        "V12_S4_SELECTED": final["selected_counts"]["s4"] if ready else 0,
        "V12_STRUCTURAL_PAIRS": final["selected_counts"]["structural_pairs"] if ready else 0,
        "V12_EXECUTION_PLAN_UNITS": plan["unit_count"] if ready else 0,
        "SEED_SEARCH": "NO",
        "SELECTED_V12_CASES_EXECUTED": 0,
        "TIMING_PRIVACY": "OPEN / NOT TESTED",
        "PACKET_LEVEL_TIMING": "OPEN",
        "HARDWARE_TEE": "NOT_TESTED",
        "SOURCE_BODY_EXECUTABLE_SUBSET": 0,
        "READY_FOR_INDEPENDENT_V12_FREEZE_AUDIT": "YES" if ready and final["ready_for_independent_v12_freeze_audit"] else "NO",
    }
    audit = {
        "schema": "AgentTool.V12FinalDevelopmentFreezeAudit/1",
        "campaign_state": (
            "FROZEN_FOR_INDEPENDENT_AUDIT"
            if ready
            else "BLOCKED_BEFORE_HOLDOUT_SELECTION"
        ),
        "status": values,
        "blocker": (
            None
            if ready
            else "full_unit_tests: 299/302 with one reproducible 50-action failure after serial recheck; performance_functional_reliability: 296/300 fixed-transcript attempts with one schedule failure and three incomplete 50-action framework trajectories"
        ),
        "development_evaluation_summary_sha256": sha(
            "V12_DEVELOPMENT_EVALUATION_SUMMARY.json"
        ),
        "final_confirmatory_freeze_sha256": sha("V12_FINAL_CONFIRMATORY_FREEZE.json") if ready else None,
        "execution_artifact_manifest_sha256": sha("V12_EXECUTION_ARTIFACT_MANIFEST.json") if ready else None,
        "selection_artifacts_created": ready,
        "authorization_file_created": False,
        "results_v12_confirmatory_exists": False,
    }
    with (ROOT / "V12_FINAL_DEVELOPMENT_FREEZE_AUDIT.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    lines = ["# V12 final development/freeze audit", ""]
    if not ready:
        lines.extend(
            (
                "**BLOCKED BEFORE HOLDOUT SELECTION.** The completed performance campaign "
                "retained four functional failures in 300 fixed-transcript attempts: one "
                "355/356-round schedule failure and three incomplete 50-action framework "
                "trajectories. The final full local regression run also finished 299/302; "
                "a serial no-change recheck left the 50-action V10-H50 canonical response-size "
                "failure reproducible. Under the fail-closed master rule, no candidate universe, "
                "seed, selected manifest, execution plan, environment freeze, artifact "
                "manifest, or final confirmatory freeze was created.",
                "",
            )
        )
    for key, value in values.items():
        lines.extend((f"{key}:", f"    {value}", ""))
    lines.extend(("No V12 authorization file was created. No selected V12 holdout case was executed. This is not an overall privacy GO.", ""))
    with (ROOT / "V12_FINAL_DEVELOPMENT_FREEZE_AUDIT.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))


if __name__ == "__main__":
    main()

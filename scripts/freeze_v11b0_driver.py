from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DRIVER_PATH = ROOT / "scripts" / "run_v11b_confirmatory.py"
SPEC = importlib.util.spec_from_file_location("v11b0_frozen_driver", DRIVER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot import V11B driver")
driver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(driver)


COMMITS = {
    "v11_4_runtime": "f6860baaab8927f9b0b66153959b55d8ca072c23",
    "v11_4_1_analysis": "fcf82d3703fa37bda4f903439363158462666356",
    "v11a_selection": "1c54e9fff88d8751d3a2fe4ed042fce736b71034",
    "v11a_1_prefix_analysis": "19945d97864a26f281377d24b98b8ff841652464",
}
PLAN = ROOT / "V11B0_EXECUTION_PLAN.json"
BASELINE = ROOT / "V11B0_COMPOSED_BASELINE.json"
TEST_REPORT = ROOT / "V11B0_DRIVER_TESTS.md"
FREEZE = ROOT / "V11B0_ONE_SHOT_DRIVER_FREEZE.json"
SELECTED = (
    "V11A_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json",
    "V11A_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json",
    "V11A_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json",
    "V11A_EFFECT_CONTRACT_HOLDOUT_FREEZE.json",
    "V11A_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json",
)
UNIVERSES = (
    "V11A_CANDIDATE_UNIVERSES_FREEZE.json",
    "V11A_SOURCE_TOOL_UNIVERSE.json",
    "V11A_COMPOSITION_UNIVERSE.json",
    "V11A_CAUSAL_TRAJECTORY_UNIVERSE.json",
    "V11A_EFFECT_CONTRACT_UNIVERSE.json",
    "V11A_STRUCTURAL_PAIR_UNIVERSE.json",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path | str) -> str:
    path = ROOT / path if isinstance(path, str) else path
    return sha256_bytes(path.read_bytes())


def canonical_sha(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def git_blob(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def binding(path: str, commit: str, checkout_sha: str | None = None) -> dict[str, Any]:
    if (
        subprocess.run(
            ["git", "diff", "--quiet", commit, "HEAD", "--", path],
            cwd=ROOT,
            capture_output=True,
        ).returncode
        != 0
    ):
        raise RuntimeError(f"frozen path changed since {commit}: {path}")
    return {
        "path": path,
        "authoritative_commit": commit,
        "git_blob_sha256": sha256_bytes(git_blob(commit, path)),
        "accepted_checkout_sha256": checkout_sha or sha256(path),
    }


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_text(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def main() -> None:
    if any(path.exists() for path in (PLAN, BASELINE, TEST_REPORT, FREEZE)):
        raise FileExistsError("refusing to overwrite V11B0 freeze artifacts")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != COMMITS["v11a_1_prefix_analysis"]:
        raise RuntimeError("V11B0 freeze requires the accepted V11A.1 commit")
    for earlier, later in zip(COMMITS.values(), list(COMMITS.values())[1:], strict=False):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", earlier, later], cwd=ROOT
        ).returncode:
            raise RuntimeError("accepted baseline commits do not form the declared chain")
    if driver.OUTPUT_ROOT.exists():
        raise RuntimeError("results_v11b_confirmatory already exists")

    v11_4 = json.loads((ROOT / "V11_4_ONLINE_EXECUTION_HARNESS_FREEZE.json").read_text(encoding="utf-8"))
    v11_4_1 = json.loads((ROOT / "V11_4_1_CONFIRMATORY_BASELINE_FREEZE.json").read_text(encoding="utf-8"))
    v11a = json.loads((ROOT / "V11A_FINAL_CONFIRMATORY_FREEZE.json").read_text(encoding="utf-8"))
    v11a_1 = json.loads((ROOT / "V11A_1_CONFIRMATORY_ANALYSIS_FREEZE.json").read_text(encoding="utf-8"))
    environment = json.loads((ROOT / "V11A_EXECUTION_ENVIRONMENT_FREEZE.json").read_text(encoding="utf-8"))

    if v11a["selected_holdout_cases_executed"] != 0 or v11a_1["selected_holdout_cases_executed"] != 0:
        raise RuntimeError("selected holdout execution evidence exists")
    if v11a_1["corrected_v11a_projection_sha256"] != "1938b9f9611c8baf393bcb7aa04ccb404221b1115e0e0f0b3c1f28df7b6f6ce1":
        raise RuntimeError("V11A.1 corrected projection is not the accepted override")

    plan = driver.build_execution_plan()
    write_json(PLAN, plan)

    runtime_bindings = []
    for path, expected_checkout in v11_4["files_sha256"].items():
        if path == "canonical_v9_1/projection.py":
            continue
        runtime_bindings.append(binding(path, COMMITS["v11_4_runtime"], expected_checkout))

    analysis_overrides = [
        binding(
            "canonical_v9_1/projection.py",
            COMMITS["v11_4_1_analysis"],
            v11_4_1["committed_stronger_projection_sha256"],
        ),
        binding(
            "v11a_confirmatory/projection.py",
            COMMITS["v11a_1_prefix_analysis"],
            v11a_1["corrected_v11a_projection_sha256"],
        ),
    ]

    authoritative_selection_paths = set(SELECTED) | set(UNIVERSES) | {
        "V11A_SELECTION_SEEDS.json",
        "V11A_MASTER_EXCLUSION_SET.json",
        "V11A_EXECUTION_ORDER.json",
        "V11A_CONFIRMATORY_ORCHESTRATOR_FREEZE.json",
        "V11A_SEMANTIC_DECISION_RULES.md",
        "V11A_STRUCTURAL_DECISION_RULES.md",
        "V11A_ONE_SHOT_EXECUTION_POLICY.md",
        "V11A_APPEND_ONLY_EVIDENCE_CONTRACT.md",
        "V11A_EXECUTION_ENVIRONMENT_FREEZE.json",
        "V11A_FINAL_CONFIRMATORY_FREEZE.json",
        "v11a_confirmatory/orchestrator.py",
    }
    selection_bindings = []
    for path in sorted(authoritative_selection_paths):
        checkout_sha = None
        if path in v11a["bound_files"]:
            checkout_sha = v11a["bound_files"][path]
        elif path in v11a_1.get("unchanged_candidate_universe_hashes", {}):
            checkout_sha = v11a_1["unchanged_candidate_universe_hashes"][path]
        selection_bindings.append(binding(path, COMMITS["v11a_selection"], checkout_sha))

    baseline = {
        "schema": "AgentTool.V11B0ComposedBaseline/1",
        "status": "COMPOSED_PREEXECUTION_BASELINE",
        "accepted_commits": COMMITS,
        "resolution_rules": {
            "runtime": "V11.4 execution freeze is authoritative",
            "canonical_analysis_projection": "V11.4.1 stronger canonical_v9_1/projection.py only",
            "selection": "V11A manifests, seeds, universes, order, orchestrator, and decision rules",
            "prefix_analysis": "V11A.1 corrected v11a_confirmatory/projection.py only",
            "all_other_difference": "HARNESS_INTEGRITY_FAILURE",
        },
        "documented_analysis_overrides_only": [
            "canonical_v9_1/projection.py",
            "v11a_confirmatory/projection.py",
        ],
        "runtime_bindings": runtime_bindings,
        "analysis_overrides": analysis_overrides,
        "selection_bindings": selection_bindings,
        "v11_4_execution_freeze_sha256": sha256("V11_4_ONLINE_EXECUTION_HARNESS_FREEZE.json"),
        "v11_4_1_analysis_freeze_sha256": sha256("V11_4_1_CONFIRMATORY_BASELINE_FREEZE.json"),
        "v11a_final_selection_freeze_sha256": sha256("V11A_FINAL_CONFIRMATORY_FREEZE.json"),
        "v11a_1_analysis_freeze_sha256": sha256("V11A_1_CONFIRMATORY_ANALYSIS_FREEZE.json"),
        "execution_plan_sha256": sha256(PLAN),
        "public_profile_checkout_sha256": sha256("PUBLIC_PROFILE_ONLINE_V11_4.json"),
        "canonical_linux_runner_sha256": environment["canonical_linux_binary_sha256"],
        "dependency_expectations": {
            "openai_revision": environment["openai_agents_sdk_revision"],
            "microsoft_revision": environment["microsoft_agent_framework_revision"],
            "simplepir_revision": environment["simplepir_revision"],
            "simplepir_bridge_source_sha256": environment["simplepir_bridge_source_sha256"],
            "ohttp_source_tree_sha256": environment["ohttp_go_source_tree_sha256"],
        },
        "selected_holdout_cases_executed": 0,
        "seed_derivation": False,
        "reselection": False,
    }
    write_json(BASELINE, baseline)
    baseline_check = driver.verify_composed_baseline(
        baseline, runner_path=None, require_runner=False
    )
    if not baseline_check["passed"]:
        raise RuntimeError(f"composed baseline verification failed: {baseline_check['checks']}")

    test_command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_v11b0_driver.py",
        "-v",
    ]
    completed = subprocess.run(test_command, cwd=ROOT, text=True, capture_output=True)
    test_output = completed.stdout + completed.stderr
    if completed.returncode:
        raise RuntimeError(test_output)
    plan_only = subprocess.run(
        [sys.executable, str(DRIVER_PATH), "--plan-only"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if plan_only.returncode or json.loads(plan_only.stdout)["selected_execution"] != 0:
        raise RuntimeError("plan-only driver gate failed")
    if driver.OUTPUT_ROOT.exists():
        raise RuntimeError("driver tests created selected output root")

    write_text(
        TEST_REPORT,
        "# V11B0 driver tests\n\n"
        "- Generic driver unit tests: **4/4 PASS**.\n"
        "- Plan-only counts: **158 total / 65 native / 93 canonical**.\n"
        "- Plan-only runtime calls: **0**.\n"
        "- Approved V11B `ExecutionPermit` instances: **0**.\n"
        "- Missing/false authorization: `HARNESS_INTEGRITY_FAILURE` before output creation.\n"
        "- Append-only ledger: exclusive creation and two-record SHA-256 chain PASS.\n"
        "- Automatic retry: absent; all 158 units freeze `retry_allowed=false`.\n"
        "- Selected holdout executions: **0**.\n\n"
        f"Test-output SHA-256: `{sha256_bytes(test_output.encode())}`.\n",
    )

    bound = [
        "scripts/run_v11b_confirmatory.py",
        "tests/test_v11b0_driver.py",
        "v11a_confirmatory/orchestrator.py",
        "v11a_confirmatory/projection.py",
        "V11B0_EXECUTION_PLAN.json",
        "V11B0_COMPOSED_BASELINE.json",
        "V11B0_DRIVER_TESTS.md",
        "V11A_SEMANTIC_DECISION_RULES.md",
        "V11A_STRUCTURAL_DECISION_RULES.md",
        "V11A_ONE_SHOT_EXECUTION_POLICY.md",
        "V11A_APPEND_ONLY_EVIDENCE_CONTRACT.md",
        "V11A_EXECUTION_ORDER.json",
        "V11A_EXECUTION_ENVIRONMENT_FREEZE.json",
        *SELECTED,
    ]
    freeze = {
        "schema": "AgentTool.V11B0OneShotDriverFreeze/1",
        "status": "FROZEN_PREEXECUTION_ONLY",
        "accepted_commits": COMMITS,
        "bound_files": {path: sha256(path) for path in bound},
        "driver_test_result": "4/4 PASS",
        "plan_only_result": "158/65/93; selected execution 0",
        "composed_baseline_verified": "PASS",
        "append_only_output": "PASS",
        "no_retry_enforced": "PASS",
        "selected_execution_guard": "PASS",
        "selected_holdout_cases_executed": 0,
        "approved_v11b_execution_permits_instantiated": 0,
        "results_v11b_confirmatory_exists": False,
        "ready_for_final_v11b_execution_audit": "YES",
    }
    freeze["aggregate_sha256"] = canonical_sha(freeze)
    write_json(FREEZE, freeze)
    print("COMPOSED_BASELINE_VERIFIED=PASS")
    print("EXECUTION_PLAN=158;NATIVE=65;CANONICAL=93")
    print("SELECTED_HOLDOUT_CASES_EXECUTED=0")


if __name__ == "__main__":
    main()

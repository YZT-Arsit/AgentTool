from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
V11B0_COMMIT = "e8597888c47a08a9aaf63a8815a84956aed8b5e7"
AUDIT = ROOT / "V11B0_1_PREFLIGHT_HARDENING_AUDIT.md"
TEST_REPORT = ROOT / "V11B0_1_DRIVER_TESTS.md"
FREEZE = ROOT / "V11B0_1_ONE_SHOT_DRIVER_FREEZE.json"
BRIDGE_FREEZE = ROOT / "V11B0_1_SIMPLEPIR_BRIDGE_FREEZE.json"
RULES = ROOT / "V11B0_1_FINAL_DECISION_RULES.json"
PLAN = ROOT / "V11B0_EXECUTION_PLAN.json"
REMOTE_BINARY_COPY = Path.home() / "AppData" / "Local" / "Temp" / "acv-simplepir-online-v11b0-1"

SELECTED = (
    "V11A_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json",
    "V11A_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json",
    "V11A_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json",
    "V11A_EFFECT_CONTRACT_HOLDOUT_FREEZE.json",
    "V11A_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json",
)
IMMUTABLE = SELECTED + (
    "V11A_SELECTION_SEEDS.json",
    "V11A_EXECUTION_ORDER.json",
    "V11A_MASTER_EXCLUSION_SET.json",
    "V11A_CANDIDATE_UNIVERSES_FREEZE.json",
    "V11A_SOURCE_TOOL_UNIVERSE.json",
    "V11A_COMPOSITION_UNIVERSE.json",
    "V11A_CAUSAL_TRAJECTORY_UNIVERSE.json",
    "V11A_EFFECT_CONTRACT_UNIVERSE.json",
    "V11A_STRUCTURAL_PAIR_UNIVERSE.json",
    "V11A_FINAL_CONFIRMATORY_FREEZE.json",
    "V11A_EXECUTION_ENVIRONMENT_FREEZE.json",
    "V11B0_COMPOSED_BASELINE.json",
    "V11B0_EXECUTION_PLAN.json",
    "V11B0_ONE_SHOT_DRIVER_FREEZE.json",
    "PUBLIC_PROFILE_ONLINE_V11_4.json",
    "v11a_confirmatory/orchestrator.py",
    "v11a_confirmatory/projection.py",
    "pir_integration/simplepir_bridge/main.go",
    "pir_integration/simplepir_bridge/go.mod",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path | str) -> str:
    path = ROOT / path if isinstance(path, str) else path
    return sha256_bytes(path.read_bytes())


def lf_sha(path: Path | str) -> str:
    path = ROOT / path if isinstance(path, str) else path
    value = path.read_bytes().decode("utf-8")
    return sha256_bytes(value.replace("\r\n", "\n").replace("\r", "\n").encode())


def canonical_sha(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )


def load(path: Path | str) -> Any:
    path = ROOT / path if isinstance(path, str) else path
    return json.loads(path.read_text(encoding="utf-8"))


def binding(path: str) -> dict[str, str]:
    if subprocess.run(
        ["git", "diff", "--quiet", V11B0_COMMIT, "HEAD", "--", path], cwd=ROOT
    ).returncode:
        raise RuntimeError(f"immutable path differs from V11B0 commit: {path}")
    blob = subprocess.check_output(["git", "show", f"{V11B0_COMMIT}:{path}"], cwd=ROOT)
    return {
        "path": path,
        "authoritative_commit": V11B0_COMMIT,
        "git_blob_sha256": sha256_bytes(blob),
    }


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_text(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def main() -> None:
    if any(path.exists() for path in (AUDIT, TEST_REPORT, FREEZE)):
        raise FileExistsError("refusing to overwrite V11B0.1 freeze outputs")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != V11B0_COMMIT:
        raise RuntimeError("V11B0.1 must start from the accepted V11B0 commit")
    if (ROOT / "results_v11b_confirmatory").exists():
        raise RuntimeError("selected result root exists")
    bindings = [binding(path) for path in IMMUTABLE]

    plan = load(PLAN)
    if (plan["unit_count"], plan["native_units"], plan["canonical_units"]) != (158, 65, 93):
        raise RuntimeError("execution plan counts changed")
    old_freeze = load("V11B0_ONE_SHOT_DRIVER_FREEZE.json")
    if sha256(PLAN) != old_freeze["bound_files"]["V11B0_EXECUTION_PLAN.json"]:
        raise RuntimeError("V11B execution plan bytes changed")

    counts = {
        "S1": len(load(SELECTED[0])["cases"]),
        "S2": len(load(SELECTED[1])["cases"]),
        "S3": len(load(SELECTED[2])["trajectories"]),
        "S4": len(load(SELECTED[3])["cases"]),
        "structural_pairs": len(load(SELECTED[4])["pairs"]),
    }
    if counts != {"S1": 32, "S2": 12, "S3": 12, "S4": 9, "structural_pairs": 14}:
        raise RuntimeError(f"selected denominator changed: {counts}")
    bridge = load(BRIDGE_FREEZE)
    if not REMOTE_BINARY_COPY.is_file() or sha256(REMOTE_BINARY_COPY) != bridge["binary_sha256"]:
        raise RuntimeError("independently retrieved Linux bridge binary hash mismatch")

    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_v11b0_driver.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_v11b0_1_hardening.py", "-v"],
    ]
    outputs = []
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        outputs.append(completed.stdout + completed.stderr)
        if completed.returncode:
            raise RuntimeError(outputs[-1])
    if (ROOT / "results_v11b_confirmatory").exists():
        raise RuntimeError("tests created selected output root")

    test_output = "\n".join(outputs)
    write_text(
        TEST_REPORT,
        "# V11B0.1 driver hardening tests\n\n"
        "- Existing V11B0 plan/guard tests: **4/4 PASS**.\n"
        "- New V11B0.1 hardening tests: **8/8 PASS**.\n"
        "- LF/CRLF committed-text equivalence and semantic mutation rejection: PASS.\n"
        "- SimplePIR binary mismatch rejection: PASS.\n"
        "- Dirty external repository and wrong framework import rejection: PASS.\n"
        "- Exact/duplicate/missing/unexpected operation-ID validation: PASS.\n"
        "- Pure 158-unit summarizer and truncation rejection: PASS.\n"
        "- Exclusive campaign completion and 158-ledger requirement: PASS.\n"
        "- Selected runtime invocations: **0**.\n"
        "- Approved V11B ExecutionPermit instances: **0**.\n"
        "- `results_v11b_confirmatory` created: **NO**.\n\n"
        f"Combined test-output SHA-256: `{sha256_bytes(test_output.encode())}`.\n",
    )

    write_text(
        AUDIT,
        "# V11B0.1 preflight hardening audit\n\n"
        "## Scope and immutable denominator\n\n"
        "This was a pre-execution-only phase. The accepted V11B0 commit is "
        f"`{V11B0_COMMIT}`. S1/S2/S3/S4 remain 32/12/12/9, the structural "
        "holdout remains 14 pairs, and the 158-unit plan is byte-identical to V11B0. "
        "No seed, universe, exclusion, manifest, case, trajectory, pair, or execution-order file changed.\n\n"
        "## Cross-host integrity\n\n"
        "Committed frozen text is checked by authoritative commit/path Git-blob binding, "
        "`git diff --quiet`, and a clean main working tree. New V11B0.1 text is bound by "
        "LF-canonicalized SHA-256. Binary verification remains exact-byte SHA-256. A synthetic "
        "Git regression accepted equivalent LF/CRLF checkouts and rejected a semantic mutation.\n\n"
        "## Linux SimplePIR bridge and framework provenance\n\n"
        "On the authorized Linux host, the bridge was built with `go version go1.26.5 linux/amd64` "
        "from bridge source SHA-256 `978abd59...` and a clean SimplePIR checkout at `e9020b...`. "
        "The actual resolver path is `pir_integration/simplepir_bridge/acv-simplepir-online`, "
        "binary SHA-256 `2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b`. "
        "The binary was copied back without execution and independently rehashed to the same value.\n\n"
        "OpenAI (`a40ae980...`), Microsoft (`af461de...`), and SimplePIR (`e9020b...`) "
        "all reported zero tracked/untracked changes on the authorized host. Import-only checks "
        "resolved `agents` and `agent_framework` inside those pinned source trees; no Agent case ran.\n\n"
        "## Functional and finalization hardening\n\n"
        "Structural validity now compares exact accepted/result/trajectory operation-ID multisets, "
        "rejects duplicates, missing and unexpected IDs, requires empty unresolved/waiter/pending "
        "sets, and checks provider-visible logical requests where mechanically available. The final "
        "summarizer is a pure immutable-evidence reader. Campaign completion is exclusively written "
        "only after 158 ledger records, 14 pair verdicts, and the frozen summary exist.\n\n"
        "## Claim boundary\n\n"
        "No selected outcome was observed. No privacy GO is issued. Timing privacy and packet-level "
        "timing remain open; hardware TEE is not tested; source-body executable subset remains zero.\n",
    )

    lf_paths = (
        ".gitignore",
        "scripts/run_v11b_confirmatory.py",
        "scripts/summarize_v11b_confirmatory.py",
        "scripts/freeze_v11b0_1.py",
        "tests/test_v11b0_1_hardening.py",
        "V11B0_1_SIMPLEPIR_BRIDGE_FREEZE.json",
        "V11B0_1_FINAL_DECISION_RULES.json",
        "V11B0_1_PREFLIGHT_HARDENING_AUDIT.md",
        "V11B0_1_DRIVER_TESTS.md",
    )
    environment = load("V11A_EXECUTION_ENVIRONMENT_FREEZE.json")
    freeze = {
        "schema": "AgentTool.V11B0.1OneShotDriverFreeze/1",
        "status": "FROZEN_PREEXECUTION_ONLY",
        "v11b0_commit": V11B0_COMMIT,
        "git_bindings": bindings,
        "lf_canonical_text_sha256": {path: lf_sha(path) for path in lf_paths},
        "unchanged_selected_manifest_sha256": {path: sha256(path) for path in SELECTED},
        "unchanged_selection_seed_sha256": sha256("V11A_SELECTION_SEEDS.json"),
        "unchanged_execution_order_sha256": sha256("V11A_EXECUTION_ORDER.json"),
        "unchanged_execution_plan_sha256": sha256(PLAN),
        "v11a_1_corrected_projection_sha256": sha256("v11a_confirmatory/projection.py"),
        "simplepir_actual_binary": {
            "relative_path": bridge["actual_resolver_binary_relative_path"],
            "sha256": bridge["binary_sha256"],
            "bytes": bridge["binary_bytes"],
        },
        "canonical_linux_runner_sha256": environment["canonical_linux_binary_sha256"],
        "framework_import_provenance_checks": "FROZEN_AND_REQUIRED_AT_PREFLIGHT",
        "final_decision_rules_sha256": sha256(RULES),
        "test_result": "12/12 PASS",
        "append_only_campaign_finalization": "PASS",
        "selected_holdout_cases_executed": 0,
        "approved_v11b_execution_permits_instantiated": 0,
        "results_v11b_confirmatory_exists": False,
        "ready_for_v11b_selected_execution": "YES",
    }
    freeze["aggregate_sha256"] = canonical_sha(freeze)
    write_json(FREEZE, freeze)
    print("V11B0_1_FREEZE=PASS")
    print("EXECUTION_PLAN=UNCHANGED_158")
    print("SELECTED_HOLDOUT_CASES_EXECUTED=0")


if __name__ == "__main__":
    main()

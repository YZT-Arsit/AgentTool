from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_OUTPUT = ROOT / "V12_APPLICATION_OBSERVABILITY_AND_DELTA_FUNCTIONAL_QUALIFICATION.json"
MARKDOWN_OUTPUT = ROOT / "V12_APPLICATION_OBSERVABILITY_AND_DELTA_FUNCTIONAL_QUALIFICATION.md"
EXCLUSIONS_OUTPUT = ROOT / "V12_APPLICATION_OBSERVABILITY_DEVELOPMENT_EXCLUSIONS.json"
EXPECTED_UNTRACKED = [
    "V12_TIMING_ATTACK_DEVELOPMENT_PROTOCOL_FREEZE.json",
    "V12_TIMING_ATTACK_MATRIX_AUDIT.json",
    "V12_TIMING_ATTACK_MATRIX_AUDIT.md",
    "V12_TIMING_ATTACK_PROJECTION_AUDIT.json",
    "V12_TIMING_ATTACK_PROJECTION_AUDIT.md",
    "V12_TIMING_V3_FUNCTIONAL_CAPACITY_MANIFEST.json",
    "V12_TIMING_V3_PROFILE_CANDIDATES_FREEZE.json",
    "scripts/analyze_v12_timing_attack.py",
    "scripts/freeze_v12_timing_attack_development.py",
    "scripts/run_v12_timing_attack_campaign.py",
    "scripts/run_v12_timing_v3_functional_capacity.py",
    "v12_timing/controls.py",
    "v12_timing/development.py",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(cwd: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=cwd, input=input_bytes, check=True, capture_output=True
    ).stdout


def git_blob(data: bytes, cwd: Path) -> str:
    return git(cwd, "hash-object", "--stdin", input_bytes=data).decode().strip()


def preserved_diff_blob(cwd: Path, *, cached: bool = False) -> str:
    """Reproduce the PowerShell-pipeline fingerprint recorded at phase start."""

    if os.name == "nt":
        diff = "git diff --cached" if cached else "git diff"
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f"{diff} | git hash-object --stdin"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    return git_blob(git(cwd, "diff", *(('--cached',) if cached else ())), cwd)


def fmt_ns(value: int) -> str:
    return f"{value} ns ({value / 1_000_000:.6f} ms)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--original-worktree", type=Path, required=True)
    parser.add_argument("--compact-archive", type=Path, required=True)
    args = parser.parse_args()
    for output in (JSON_OUTPUT, MARKDOWN_OUTPUT, EXCLUSIONS_OUTPUT):
        if output.exists():
            raise FileExistsError(f"refusing to overwrite append-only evidence: {output}")

    phase = json.loads((args.evidence_root / "phase_summary.json").read_text(encoding="utf-8"))
    preserved = json.loads((ROOT / "V12_ORIGINAL_WORKTREE_PRESERVATION.json").read_text(encoding="utf-8"))
    original = args.original_worktree.resolve()
    current_head = git(original, "rev-parse", "HEAD").decode().strip()
    tracked = preserved_diff_blob(original)
    cached = preserved_diff_blob(original, cached=True)
    untracked = git(original, "ls-files", "--others", "--exclude-standard").decode().splitlines()
    original_preserved = (
        current_head == preserved["head"]
        and tracked == preserved["tracked_diff_git_blob"]
        and cached == preserved["cached_diff_git_blob"]
        and sorted(untracked) == sorted(EXPECTED_UNTRACKED)
        and len(untracked) == preserved["untracked_count"]
    )
    if not original_preserved:
        raise RuntimeError("original dirty worktree preservation check failed")

    profiles = phase["profiles"]
    if set(profiles) != {"10", "20", "25"}:
        raise RuntimeError("frozen Delta set changed")
    if any(row["status"] != "FUNCTIONALLY_ELIGIBLE" or row["workloads_passed"] != 8
           or row["workloads_total"] != 8 for row in profiles.values()):
        raise RuntimeError("functional qualification did not close 8/8 for every Delta")
    if len(phase["units"]) != 24 or any(
        not row["common_integrity_pass"] or not row["functional_pass"] for row in phase["units"]
    ):
        raise RuntimeError("functional unit evidence is incomplete")
    prohibited = phase["prohibited_execution"]
    if prohibited["classifier_training_runs_on_real_traces"] != 0 or prohibited["real_timing_auc_calculations"] != 0:
        raise RuntimeError("prohibited statistical execution was recorded")

    result = {
        **phase,
        "dirty_original_worktree_preserved": "YES",
        "clean_phase_worktree": "PASS",
        "original_worktree_final_fingerprint": {
            "head": current_head,
            "tracked_diff_git_blob": tracked,
            "cached_diff_git_blob": cached,
            "untracked_paths": untracked,
            "untracked_count": len(untracked),
            "baseline_untracked_manifest_git_blob": preserved["untracked_manifest_git_blob"],
        },
        "compact_evidence_archive": {
            "filename": args.compact_archive.name,
            "sha256": sha(args.compact_archive),
        },
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
        "packet_level_timing": "OPEN",
        "hardware_tee": "NOT_TESTED",
        "ready_for_local_control_sensitivity_evaluation": "YES",
        "ready_for_protected_statistical_evaluation": "NO_IN_THIS_PHASE",
        "ready_for_final_v12_holdout": "NO",
    }
    result["payload_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    JSON_OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")

    exclusions = {
        "schema": "AgentTool.V12ApplicationObservabilityDevelopmentExclusions/1",
        "phase": phase["phase"],
        "identities": [row["identity"] for row in phase["units"]],
        "identity_count": len(phase["units"]),
        "future_confirmatory_and_holdout_exclusion_required": True,
        "does_not_construct_a_confirmatory_or_final_universe": True,
    }
    EXCLUSIONS_OUTPUT.write_text(json.dumps(exclusions, indent=2) + "\n", encoding="utf-8", newline="\n")

    rows = []
    for period in (10, 20, 25):
        row = profiles[str(period)]
        slip = row["launch_slip_ns"]
        gaps = row["registry_inter_query_gap_ns"]
        response = row["registry_request_response_ns"]
        span = row["session_wall_clock_span_ns"]
        rows.append(
            f"| P{period} | {row['status']} | {row['workloads_passed']}/{row['workloads_total']} | "
            f"{row['nominal_late_cell_total']} | {slip['p50']}/{slip['p95']}/{slip['p99']}/{slip['max']} | "
            f"{span['p50']}/{span['p95']}/{span['p99']}/{span['max']} | "
            f"{gaps['p50']}/{gaps['p95']}/{gaps['p99']}/{gaps['max']} | "
            f"{response['p50']}/{response['p95']}/{response['p99']}/{response['max']} | "
            f"{row['relay_response_send_completeness']} + {row['registry_response_send_completeness']} |"
        )
    markdown = f"""# V12 application observability and Delta functional qualification

Execution commit: `{phase['execution_commit']}`. Base methodology commit: `{phase['base_methodology_commit']}`.

All three frozen H4500 candidates passed their fresh 8/8 integrated functional matrices. This result establishes only
observability-complete functional eligibility. It does not select a Delta and does not support a timing-privacy verdict.

| Candidate | Functional status | Workloads | Nominal late cells | Launch slip p50/p95/p99/max (ns) | Session span p50/p95/p99/max (ns) | Registry gap p50/p95/p99/max (ns) | Registry response p50/p95/p99/max (ns) | Send completeness Relay + Registry |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

Decisive software gates passed: Python serial `100/100`, Python default `100/100`, native routing `15/15`, Go `83/83`,
and security negatives `22/22` (`15` Python plus `7` frozen Go negatives). Deployment integrity matched `691/691`
files, `8/8` Python module probes, and `2/2` runtime binaries. The original dirty worktree remained unchanged.

The preliminary missing-binary skips, V3 test-fixture compile failure, and unmaterialized-framework module-probe failure
remain recorded in the JSON evidence and were excluded from decisive results. They occurred before any functional identity.

## Required closure fields

```text
BASE_METHODOLOGY_COMMIT: {phase['base_methodology_commit']}
DIRTY_ORIGINAL_WORKTREE_PRESERVED: YES
CLEAN_PHASE_WORKTREE: PASS
METHODOLOGY_AUC_ORIENTATION_ERRATUM: PASS
DISTINGUISHABILITY_AUC: max(AUC, 1-AUC)
REGISTRY_RESPONSE_SEND_INSTRUMENTATION: PASS
RELAY_RESPONSE_SEND_INSTRUMENTATION: PASS
COMPLETE_APPLICATION_TIMING_VIEW: PASS
EFFECTIVE_PUBLIC_CLOCK_V3: PASS
P10_PROFILE: H4500 / Delta10 / R506
P20_PROFILE: H4500 / Delta20 / R279
P25_PROFILE: H4500 / Delta25 / R233
P10_DETERMINISTIC_CAPACITY: PASS
P20_DETERMINISTIC_CAPACITY: PASS
P25_DETERMINISTIC_CAPACITY: PASS
POST_CHANGE_PYTHON_SERIAL: 100 / 100
POST_CHANGE_PYTHON_DEFAULT: 100 / 100
POST_CHANGE_NATIVE_ROUTING: 15 / 15
POST_CHANGE_GO: 83 / 83
POST_CHANGE_SECURITY_NEGATIVES: 22 / 22
TRANSITIVE_RUNTIME_HASH_MATCH: 691 / 691 files + 8 / 8 module probes + 2 / 2 binaries
P10_FUNCTIONAL: FUNCTIONALLY_ELIGIBLE
P20_FUNCTIONAL: FUNCTIONALLY_ELIGIBLE
P25_FUNCTIONAL: FUNCTIONALLY_ELIGIBLE
P10_NOMINAL_LATENESS: total 2852; launch-slip p50/p95/p99/max 18022786/39102139/46507437/48792501 ns
P20_NOMINAL_LATENESS: total 174; launch-slip p50/p95/p99/max 9939537/22015651/24609537/26191163 ns
P25_NOMINAL_LATENESS: total 0; launch-slip p50/p95/p99/max 10405228/19451527/20451140/21290230 ns
CLASSIFIER_TRAINING_RUNS_ON_REAL_TRACES: 0
REAL_TIMING_AUC_CALCULATIONS: 0
TIMING_CONFIRMATORY_SESSIONS: 0
SELECTED_TIMING_DELTA_MS: NONE
TIMING_PRIVACY: INCONCLUSIVE
TIMING_GO: NO
PACKET_LEVEL_TIMING: OPEN
HARDWARE_TEE: NOT_TESTED
FINAL_B4_B5: NOT_RUN
V12_FINAL_CANDIDATE_UNIVERSE_EXISTS: NO
V12_FINAL_SEED_EXISTS: NO
SELECTED_FINAL_V12_CASES_EXECUTED: 0
READY_FOR_LOCAL_CONTROL_SENSITIVITY_EVALUATION: YES
READY_FOR_PROTECTED_STATISTICAL_EVALUATION: NO in this phase
READY_FOR_FINAL_V12_HOLDOUT: NO
```
"""
    MARKDOWN_OUTPUT.write_text(markdown, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import copy
import csv
import difflib
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from canonical_v9_1.projection import strict_size_projection, strict_structural_projection
from v11_4.profile import selected_profile


BASE_COMMIT = "f6860baaab8927f9b0b66153959b55d8ca072c23"
EXECUTION_FREEZE = ROOT / "V11_4_ONLINE_EXECUTION_HARNESS_FREEZE.json"
PROFILE_PATH = ROOT / "PUBLIC_PROFILE_ONLINE_V11_4.json"
COMMITTED_PROJECTION = ROOT / "canonical_v9_1" / "projection.py"
TRANSFER_ARCHIVE = ROOT / "tmp" / "v11_4_1_projection_raw.tgz"
TRANSFER_ROOT = ROOT / "tmp" / "v11_4_1_projection_raw"
LINUX_PROJECTION = TRANSFER_ROOT / "canonical_v9_1" / "projection.py"
RAW_ROOT = TRANSFER_ROOT / "results_v11_4_development"
RESULTS = ROOT / "results_v11_4_1_alignment"

EXPECTED_ARCHIVE_SHA256 = "f5ac03c3fb643efb630c9e487d197896d8151fa1355da2d092f0738e069b85ce"
EXPECTED_OLD_PROJECTION_SHA256 = "4b1181261eb012e9554b69538e371a1f12bd8e4364024c10022160d5bd0e0655"
EXPECTED_COMMITTED_PROJECTION_SHA256 = "3a9fc710f98c586e98be64b04e5c8875f8297906199458199340b41fb981f9ea"
EXPECTED_PROFILE_SHA256 = "1bc17974513a0217437ec3d4e8606af9db59fcf22229d20165dfe639a30e24ea"
EXPECTED_BINARY_SHA256 = "14eb0488813425a99e49ac74741777fb5022a04ada6577a5b00bb5d2ef119877"
EXPECTED_ADDITIONS = {
    '"public_session_ids": [int(event.get("session", 1)) for event in events],',
    '"client_http_versions": [str(event.get("client_http_version", "")) for event in events],',
    '"gateway_http_versions": [str(event.get("gateway_http_version", "")) for event in events],',
}

PAIR_PATHS = {
    "AGENT_IDENTITY": "post_gate_repair_raw/agent_identity_v2",
    "TOOL_ROUTE": "structural_raw/tool_route",
    "ACTION_KIND": "structural_raw/action_kind",
    "ACTION_COUNT": "structural_raw/action_count",
    "REPETITION": "structural_raw/repetition",
    "FREQUENCY": "structural_raw/frequency",
    "RARE_TARGET": "structural_raw/rare_target",
    "TRANSITION_PATTERN": "structural_raw/transition_pattern",
    "ARGUMENT_LENGTH": "structural_raw/argument_length",
    "PROVIDER_READINESS": "structural_raw/provider_readiness",
    "INTERNAL_EXTERNAL": "structural_raw/internal_external",
    "CAUSAL_DEPTH": "structural_raw/causal_depth",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def load_old_projection_module():
    # Give the retrieved module its original package context so its frozen
    # relative import of ``.profile`` resolves to the existing package.  The
    # retrieved file is read-only analysis code and is never installed over
    # the committed projection.
    spec = importlib.util.spec_from_file_location("canonical_v9_1.projection_linux_frozen", LINUX_PROJECTION)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Linux-frozen projection")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def semantic_diff() -> dict[str, Any]:
    old_lines = LINUX_PROJECTION.read_text(encoding="utf-8").splitlines()
    new_lines = COMMITTED_PROJECTION.read_text(encoding="utf-8").splitlines()
    diff = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="linux-frozen/canonical_v9_1/projection.py",
            tofile=f"git-{BASE_COMMIT}/canonical_v9_1/projection.py",
            lineterm="",
        )
    )
    additions = {
        line[1:].strip()
        for line in diff
        if line.startswith("+") and not line.startswith("+++")
    }
    removals = {
        line[1:].strip()
        for line in diff
        if line.startswith("-") and not line.startswith("---")
    }
    exact = additions == EXPECTED_ADDITIONS and not removals
    return {
        "exactly_expected_three_additions": exact,
        "additions": sorted(additions),
        "removals": sorted(removals),
        "unified_diff": diff,
    }


def profile_event_gate(trace: dict[str, Any]) -> dict[str, bool]:
    events = trace["public_relay_events"]
    projection_keys = set(strict_structural_projection(trace, selected_profile(10, 3000)))
    actual_timing_fields = {
        "request_observed_ns",
        "response_observed_ns",
        "scheduled_send_ns",
        "actual_socket_send_ns",
        "actual_socket_receive_ns",
        "release_slip_ns",
        "launch_slip_ns",
    }
    return {
        "authenticated_public_order": [
            (int(event["session"]), int(event["round"])) for event in events
        ] == [(1, index) for index in range(1, 357)],
        "public_session_ids": [int(event["session"]) for event in events] == [1] * 356,
        "client_http_versions": [str(event["client_http_version"]) for event in events] == ["HTTP/2.0"] * 356,
        "gateway_http_versions": [str(event["gateway_http_version"]) for event in events] == ["HTTP/2.0"] * 356,
        "request_lengths": [int(event["request_length"]) for event in events] == [1079] * 356,
        "response_lengths": [int(event["response_length"]) for event in events] == [800] * 356,
        # The public configured lifetime is part of Gamma and is intentionally
        # represented in nanoseconds.  Only measured/actual timing fields are
        # forbidden from structural equality.
        "timestamp_excluded_from_projection": projection_keys.isdisjoint(actual_timing_fields),
    }


def frozen_summary(pair: str, arm: str) -> dict[str, Any]:
    relative = PAIR_PATHS[pair]
    return json.loads(
        (ROOT / "results_v11_4_development" / relative / arm / "v11_3_development_summary.json").read_text(
            encoding="utf-8"
        )
    )


def raw_trace(pair: str, arm: str) -> tuple[Path, dict[str, Any]]:
    path = RAW_ROOT / PAIR_PATHS[pair] / arm / "go_online_result.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if RESULTS.exists():
        raise FileExistsError(f"refusing to overwrite alignment evidence: {RESULTS}")
    RESULTS.mkdir()
    if git_head() != BASE_COMMIT:
        raise AssertionError("working tree is not at the accepted V11.4 base commit")
    if sha256(TRANSFER_ARCHIVE) != EXPECTED_ARCHIVE_SHA256:
        raise AssertionError("retrieved raw-trace archive hash mismatch")
    if sha256(LINUX_PROJECTION) != EXPECTED_OLD_PROJECTION_SHA256:
        raise AssertionError("Linux-frozen projection hash mismatch")
    if sha256(COMMITTED_PROJECTION) != EXPECTED_COMMITTED_PROJECTION_SHA256:
        raise AssertionError("committed stronger projection hash mismatch")
    if sha256(PROFILE_PATH) != EXPECTED_PROFILE_SHA256:
        raise AssertionError("V11.4 final public profile hash mismatch")
    if sha256(EXECUTION_FREEZE) != "3d919523daac5b366b326755019f06d93caf6dd6a487ca6c75fa4c20638466c3":
        raise AssertionError("original V11.4 execution-freeze file changed")

    diff = semantic_diff()
    if not diff["exactly_expected_three_additions"]:
        raise AssertionError("projection diff contains semantics beyond the three intended public fields")

    evidence_dir = RESULTS / "retrieved_linux_frozen_evidence"
    evidence_dir.mkdir()
    shutil.copyfile(LINUX_PROJECTION, evidence_dir / "projection.py")
    old_module = load_old_projection_module()
    profile = selected_profile(10, 3000)
    accepted = {
        row["pair"]: row
        for row in csv.DictReader(
            (ROOT / "results_v11_4_development" / "structural_regression_effective.csv").open(encoding="utf-8")
        )
    }

    rows: list[dict[str, Any]] = []
    raw_inventory: list[dict[str, str]] = []
    for pair, relative in PAIR_PATHS.items():
        arm_values: dict[str, dict[str, Any]] = {}
        for arm in ("A", "B"):
            path, trace = raw_trace(pair, arm)
            raw_inventory.append(
                {"pair": pair, "arm": arm, "path": str(path.relative_to(TRANSFER_ROOT)).replace("\\", "/"), "sha256": sha256(path)}
            )
            gate = profile_event_gate(trace)
            if not all(gate.values()):
                raise AssertionError(f"{pair}/{arm} failed stronger public-field invariants: {gate}")
            stronger = strict_structural_projection(trace, profile)
            old = old_module.strict_structural_projection(trace, profile)
            stronger_without_additions = {
                key: value
                for key, value in stronger.items()
                if key not in {"public_session_ids", "client_http_versions", "gateway_http_versions"}
            }
            current_size = strict_size_projection(trace, profile)
            old_size = old_module.strict_size_projection(trace, profile)
            frozen_size = frozen_summary(pair, arm)["strict_size_projection"]
            arm_values[arm] = {
                "stronger": stronger,
                "old": old,
                "size": current_size,
                "gate": gate,
                "old_projection_preserved": stronger_without_additions == old,
                "size_unchanged": current_size == old_size == frozen_size,
                "runtime_complete": trace["session_status"] == "COMPLETE",
                "schedule_misses": int(trace["schedule_misses"]),
                "profile_overflow": int(trace["profile_overflow_events"]),
                "dummy_provider_operations": int(trace["dummy_provider_operations"]),
                "silent_loss": int(trace["silent_committed_result_losses"]),
            }
        a, b = arm_values["A"], arm_values["B"]
        accepted_pair = str(accepted[pair]["passed"]).lower() == "true"
        row = {
            "pair": pair,
            "accepted_v11_4_pair": accepted_pair,
            "arm_a_runtime_complete": a["runtime_complete"],
            "arm_b_runtime_complete": b["runtime_complete"],
            "authenticated_public_order": a["gate"]["authenticated_public_order"] and b["gate"]["authenticated_public_order"],
            "public_session_ids_exact": a["gate"]["public_session_ids"] and b["gate"]["public_session_ids"],
            "client_http_versions_exact": a["gate"]["client_http_versions"] and b["gate"]["client_http_versions"],
            "gateway_http_versions_exact": a["gate"]["gateway_http_versions"] and b["gate"]["gateway_http_versions"],
            "request_lengths_exact": a["gate"]["request_lengths"] and b["gate"]["request_lengths"],
            "response_lengths_exact": a["gate"]["response_lengths"] and b["gate"]["response_lengths"],
            "timestamp_excluded": a["gate"]["timestamp_excluded_from_projection"] and b["gate"]["timestamp_excluded_from_projection"],
            "old_projection_fields_preserved": a["old_projection_preserved"] and b["old_projection_preserved"],
            "strict_size_projection_unchanged": a["size_unchanged"] and b["size_unchanged"],
            "stronger_structural_equal": a["stronger"] == b["stronger"],
            "stronger_size_equal": a["size"] == b["size"],
            "schedule_misses": a["schedule_misses"] + b["schedule_misses"],
            "profile_overflow": a["profile_overflow"] + b["profile_overflow"],
            "dummy_provider_operations": a["dummy_provider_operations"] + b["dummy_provider_operations"],
            "silent_committed_result_loss": a["silent_loss"] + b["silent_loss"],
        }
        row["passed"] = all(
            bool(row[key])
            for key in (
                "accepted_v11_4_pair",
                "arm_a_runtime_complete",
                "arm_b_runtime_complete",
                "authenticated_public_order",
                "public_session_ids_exact",
                "client_http_versions_exact",
                "gateway_http_versions_exact",
                "request_lengths_exact",
                "response_lengths_exact",
                "timestamp_excluded",
                "old_projection_fields_preserved",
                "strict_size_projection_unchanged",
                "stronger_structural_equal",
                "stronger_size_equal",
            )
        ) and all(int(row[key]) == 0 for key in ("schedule_misses", "profile_overflow", "dummy_provider_operations", "silent_committed_result_loss"))
        rows.append(row)

    passed = sum(bool(row["passed"]) for row in rows)
    alignment_pass = passed == 12
    csv_path = ROOT / "V11_4_1_STRUCTURAL_RECOMPUTE.csv"
    write_csv(csv_path, rows)
    write_json(RESULTS / "raw_trace_inventory.json", raw_inventory)

    diff_report = """# V11.4.1 projection diff

The exact Linux-frozen `canonical_v9_1/projection.py` was retrieved read-only from the V11.4 qualification host. Its SHA-256 is `{old_hash}`. The projection committed at `{commit}` has SHA-256 `{new_hash}`.

The semantic diff contains exactly three additions and no removals:

- `public_session_ids`
- `client_http_versions`
- `gateway_http_versions`

No other code or projection semantics differ. The committed stronger projection is therefore adopted as the candidate final analysis projection; the three fields were not removed to recover the old hash. Raw timestamp fields remain evidence but are absent from structural and size equality.

```diff
{diff_text}
```
""".format(
        old_hash=EXPECTED_OLD_PROJECTION_SHA256,
        commit=BASE_COMMIT,
        new_hash=EXPECTED_COMMITTED_PROJECTION_SHA256,
        diff_text="\n".join(diff["unified_diff"]),
    )
    (ROOT / "V11_4_1_PROJECTION_DIFF.md").write_text(diff_report, encoding="utf-8")

    recompute_report = f"""# V11.4.1 stronger structural recomputation

Status: **{passed}/12** accepted V11.4 structural-development pairs remain exactly equal under the stronger committed projection.

No workload was rerun. The analysis read 24 immutable `go_online_result.json` records from the V11.4 qualification host. Each raw event sequence was first required to be exactly authenticated public order `(session=1, round=1..356)`; wall-clock completion order and timestamps are not projection inputs.

Every accepted trace has exactly 356 session IDs equal to `1`, 356 client and Gateway HTTP versions equal to `HTTP/2.0`, 356 requests of 1079 bytes, and 356 responses of 800 bytes. `StrictSizeProjection` is byte-for-byte equal to both the Linux-frozen projection result and the previously stored V11.4 size projection for every arm.

No scheduler miss, overflow, dummy provider operation, or silent committed-result loss was observed in these accepted arms.
"""
    (ROOT / "V11_4_1_STRUCTURAL_RECOMPUTE.md").write_text(recompute_report, encoding="utf-8")

    alignment = {
        "schema": "AgentTool.V11_4_1.AnalysisBaselineAlignment/1",
        "baseline_alignment": "PASS" if alignment_pass else "FAIL",
        "v11_4_base_commit": BASE_COMMIT,
        "v11_4_runtime_rerun": False,
        "retrieved_archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "linux_frozen_projection_sha256": EXPECTED_OLD_PROJECTION_SHA256,
        "committed_stronger_projection_sha256": EXPECTED_COMMITTED_PROJECTION_SHA256,
        "semantic_diff_exactly_expected": diff["exactly_expected_three_additions"],
        "stronger_structural_recompute": f"{passed}/12",
        "strict_size_projection_unchanged": all(bool(row["strict_size_projection_unchanged"]) for row in rows),
        "timestamps_in_structural_equality": False,
        "holdout_selected": 0,
        "holdout_executed": 0,
        "v11a_preselection_audit_classification": "ABORTED_BEFORE_SELECTION_PROJECTION_BASELINE_MISMATCH",
    }
    write_json(ROOT / "V11_4_1_ANALYSIS_BASELINE_ALIGNMENT.json", alignment)

    freeze = {
        "schema": "AgentTool.V11_4_1.ConfirmatoryBaselineFreeze/1",
        "status": "FROZEN_AFTER_STRONGER_PROJECTION_RECOMPUTE_PASS" if alignment_pass else "FAILED_NOT_FROZEN",
        "v11_4_base_commit": BASE_COMMIT,
        "v11_4_execution_freeze_path": EXECUTION_FREEZE.name,
        "v11_4_execution_freeze_sha256": sha256(EXECUTION_FREEZE),
        "old_linux_projection_sha256": EXPECTED_OLD_PROJECTION_SHA256,
        "committed_stronger_projection_path": "canonical_v9_1/projection.py",
        "committed_stronger_projection_sha256": EXPECTED_COMMITTED_PROJECTION_SHA256,
        "public_profile_path": PROFILE_PATH.name,
        "public_profile_sha256": EXPECTED_PROFILE_SHA256,
        "linux_canonical_binary_sha256": EXPECTED_BINARY_SHA256,
        "stronger_structural_recompute": {"passed": passed, "total": 12},
        "strict_size_projection_unchanged": all(bool(row["strict_size_projection_unchanged"]) for row in rows),
        "raw_trace_inventory_sha256": sha256(RESULTS / "raw_trace_inventory.json"),
        "recompute_csv_sha256": sha256(csv_path),
        "analysis_alignment_sha256": sha256(ROOT / "V11_4_1_ANALYSIS_BASELINE_ALIGNMENT.json"),
        "holdout_selected": 0,
        "holdout_executed": 0,
        "timing_privacy": "OPEN / NOT TESTED",
        "packet_level_timing": "OPEN",
        "hardware_tee": "NOT_TESTED",
        "v11_4_runtime_freeze_valid": "PASS" if alignment_pass else "FAIL",
        "v11_4_analysis_projection_aligned": "PASS" if alignment_pass else "FAIL",
        "v11a_restart_allowed": "YES" if alignment_pass else "NO",
    }
    write_json(ROOT / "V11_4_1_CONFIRMATORY_BASELINE_FREEZE.json", freeze)
    print(f"BASELINE_ALIGNMENT={'PASS' if alignment_pass else 'FAIL'}")
    print(f"STRONGER_STRUCTURAL_RECOMPUTE={passed}/12")
    print(f"V11A_RESTART_ALLOWED={'YES' if alignment_pass else 'NO'}")


if __name__ == "__main__":
    main()

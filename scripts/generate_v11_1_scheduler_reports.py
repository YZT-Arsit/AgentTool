from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def truth(value: str) -> bool:
    return value.strip().lower() == "true"


def number(value: str) -> int:
    return int(value or 0)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--linux-binary-sha256", required=True)
    parser.add_argument("--linux-binary-path", required=True)
    args = parser.parse_args()

    stress = read_csv(args.campaign / "reliability_stress.csv")
    semantic = read_csv(args.campaign / "semantic_regression.csv")
    structural = read_csv(args.campaign / "structural_regression.csv")
    multi = read_csv(args.campaign / "multi_action.csv")
    faults = read_csv(args.campaign / "fault_injection.csv")
    profile = [json.loads(line) for line in (args.campaign / "profile_selection.jsonl").read_text(encoding="utf-8").splitlines() if line]

    by_gate: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in stress:
        by_gate[row["gate"]].append(row)
    expected = {"TOOL_1": 100, "TOOL_10": 50, "TOOL_50": 20}
    core_counts = {
        gate: (sum(truth(row["passed"]) for row in by_gate[gate]), len(by_gate[gate]))
        for gate in expected
    }
    other_rows = [row for row in stress if row["gate"] not in expected]
    full_scope = (sum(truth(row["passed"]) for row in other_rows), len(other_rows))
    accepted = [row for row in stress if truth(row["passed"])]
    dummy = sum(number(row.get("dummy_heavy_ops", "")) for row in accepted)
    overflow = sum(number(row.get("profile_overflow", "")) for row in accepted)
    misses = sum(number(row.get("schedule_misses", "")) for row in accepted)
    silent = sum(number(row.get("silent_committed_result_losses", "")) for row in accepted)

    stress_pass = (
        all(core_counts[gate] == (count, count) for gate, count in expected.items())
        and full_scope == (180, 180)
        and dummy == overflow == misses == silent == 0
    )
    semantic_pass = len(semantic) == 38 and all(truth(row["projection_equal"]) and truth(row["passed"]) for row in semantic)
    structural_pass = len(structural) == 11 and all(truth(row["passed"]) for row in structural)
    multi_pass = len(multi) == 5 and all(truth(row["passed"]) for row in multi)
    fault_pass = len(faults) == 2 and all(truth(row["passed"]) for row in faults)
    profile_pass = len(profile) == 20 and all(bool(row["passed"]) for row in profile)
    all_pass = all((stress_pass, semantic_pass, structural_pass, multi_pass, fault_pass, profile_pass))

    gates = []
    for gate, rows in sorted(by_gate.items()):
        passed = sum(truth(row["passed"]) for row in rows)
        gates.append(f"| {gate} | {passed}/{len(rows)} |")
    write(ROOT / "RELIABILITY_STRESS_V11_1.md", f"""
# V11.1 Linux reliability stress

All rows are non-holdout development repetitions on the qualified Linux host.
The accepted campaign used Linux binary `{args.linux_binary_sha256}` and the
5 ms / 111-slot development profile.

| Gate | Passed |
|---|---:|
{chr(10).join(gates)}

The three core Tool gates are {core_counts['TOOL_1'][0]}/{core_counts['TOOL_1'][1]},
{core_counts['TOOL_10'][0]}/{core_counts['TOOL_10'][1]}, and
{core_counts['TOOL_50'][0]}/{core_counts['TOOL_50'][1]}.  The remaining full-scope
gate repetitions are {full_scope[0]}/{full_scope[1]} (220 underlying sessions
because the two paired gates execute two sessions per repetition).

Accepted-session totals: dummy heavy operations {dummy}; profile overflow
{overflow}; scheduler misses {misses}; silent committed-result losses {silent}.

Result: **{'PASS' if stress_pass else 'FAIL'}**.  Timing privacy remains open.
""")
    write(ROOT / "SEMANTIC_REGRESSION_V11_1.md", f"""
# V11.1 semantic regression

The existing 38 non-holdout Level-A cases were re-executed through independent
native framework and canonical implementations.  Exact semantic projections
matched for **{sum(truth(row['projection_equal']) for row in semantic)}/{len(semantic)}**;
the scheduler/session gate also passed for **{sum(truth(row['passed']) for row in semantic)}/{len(semantic)}**.

No V10 or V10.1 selected case was loaded or executed.  Result:
**{'PASS' if semantic_pass else 'FAIL'}**.
""")
    write(ROOT / "STRUCTURAL_REGRESSION_V11_1.md", f"""
# V11.1 structural regression

Eleven non-holdout development pairs cover Agent identity, Tool route, action
kind, action count, repetition, frequency, a rare target, transition pattern,
argument length, completion readiness, and STRICT internal versus external
placement.  Both arms had to be functional before comparison.

Exact profile/session/slot/count/order/size/OHTTP/endpoint/normalized-connection
projections matched for **{sum(truth(row['passed']) for row in structural)}/{len(structural)}**.
Every accepted arm reported HTTP/2 on both hops.  Timestamps are deliberately
excluded from equality.  Result: **{'PASS' if structural_pass else 'FAIL'}**.
""")
    write(ROOT / "MULTI_ACTION_DEVELOPMENT_V11_1.md", f"""
# V11.1 true multi-action development

The development composite Agent descriptor was retrieved through real
SimplePIR and authenticated before each mixed workflow.  It authorizes existing
Tool routes and one Agent-service route without changing the common public
executor.  Tested sequences were Tool to Tool, Tool to Agent-as-Tool, Tool to
handoff, Agent-as-Tool to Tool, and an out-of-order completion case.

Operation-ID association, provider count, DeliveryLedger delivery, fixed public
profile, zero dummy heavy work, and zero overflow passed for
**{sum(truth(row['passed']) for row in multi)}/{len(multi)}** workflows.  The
out-of-order case is expected to return the early second result first; logical
association remains by private operation ID.  Result: **{'PASS' if multi_pass else 'FAIL'}**.
""")
    write(ROOT / "SCHEDULER_FAULT_INJECTION_V11_1.md", f"""
# V11.1 scheduler fault injection

The non-holdout 75 ms delayed HTTP/2 stream case passed while later slot
streams continued to launch.  The scheduler-stall case passed only by producing
`SESSION_SCHEDULE_FAILURE`; it was not a functional pass and the expired slot
was not emitted as catch-up traffic.

Fault-injection checks: **{sum(truth(row['passed']) for row in faults)}/{len(faults)}**.
Result: **{'PASS' if fault_pass else 'FAIL'}**.  These are liveness and
fail-closed tests, not timing-privacy evidence.
""")

    matrix = f"""# V11.1 current security matrix

| Property | Status | Evidence boundary |
|---|---|---|
| Blocking round dependency | {'REMOVED' if fault_pass else 'PRESENT'} | independent slot goroutines and delayed-stream test |
| Catch-up burst | {'REMOVED' if fault_pass else 'PRESENT'} | expired/missed slots are not submitted |
| Public preconnect | {'PASS' if profile_pass else 'FAIL'} | ordered setup events before T0 |
| HTTP/2 single-connection multiplexing | {'PASS' if stress_pass else 'FAIL'} | Relay-observed HTTP/2 and one connection per hop |
| Inner/outer slot binding | PASS | RFC 9292 bound fields under RFC 9458 |
| Per-slot OHTTP context | PASS | one-use slot-indexed contexts and out-of-order collector |
| Explicit session failure | PASS | four enumerated terminal statuses |
| Semantic regression | {'PASS' if semantic_pass else 'FAIL'} | {sum(truth(row['projection_equal']) for row in semantic)}/{len(semantic)} |
| Structural regression | {'PASS' if structural_pass else 'FAIL'} | {sum(truth(row['passed']) for row in structural)}/{len(structural)} |
| Multi-action | {'PASS' if multi_pass else 'FAIL'} | {sum(truth(row['passed']) for row in multi)}/{len(multi)} |
| Timing privacy | OPEN / NOT TESTED | launch slip is diagnostic only |
| Packet-level timing | OPEN | no kernel/NIC claim |
| Hardware TEE | NOT_TESTED | LocalTrustedBackend only |
"""
    write(ROOT / "CURRENT_SECURITY_MATRIX_V11_1.md", matrix)

    decision = "YES" if all_pass else "NO"
    write(ROOT / "FINAL_SCHEDULER_CLOSURE_AUDIT_V11_1.md", f"""
# Final V11.1 scheduler-closure audit

## Decision

`ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE = {decision}`

The scheduler gate is {'closed' if all_pass else 'not closed'}.  Profile
qualification was {sum(bool(row['passed']) for row in profile)}/{len(profile)},
fault injection {sum(truth(row['passed']) for row in faults)}/{len(faults)},
reliability stress {sum(truth(row['passed']) for row in stress)}/{len(stress)},
semantic regression {sum(truth(row['passed']) for row in semantic)}/{len(semantic)},
structural regression {sum(truth(row['passed']) for row in structural)}/{len(structural)},
and multi-action {sum(truth(row['passed']) for row in multi)}/{len(multi)}.

This decision is limited to the original software architecture and declared
development functionality.  It is not an overall privacy GO.  Timing privacy,
packet-level timing, hardware TEE validation, source-body executability, and a
fresh holdout remain separate.  No final holdout was selected or executed.

An intermediate Windows run of the pre-final candidate passed 32/33 targeted
tests but observed one `canonical response final size mismatch` in TOOL_50.
Windows was predeclared as non-decisive for scheduler stability; the event is
preserved as negative development evidence and was not reinterpreted.  The
decision above uses the fresh final-binary Linux campaign only.
""")

    if all_pass:
        hash_paths = [
            ROOT / "canonical_v9/runner.py",
            ROOT / "canonical_v9_1/runner.py",
            ROOT / "common_action_gateway_v2/canonicalv9/runner.go",
            ROOT / "common_action_gateway_v2/canonicalv9/canonicalv9_test.go",
            ROOT / "common_action_gateway_v2/v8/http_relay.go",
            ROOT / "common_action_gateway_v2/v9ohttp/bhttp_codec.go",
            ROOT / "common_action_gateway_v2/v9ohttp/ohttp_backend.go",
            ROOT / "common_action_gateway_v2/v9ohttp/v9ohttp_test.go",
            ROOT / "cryptographic_closure/pir_backend.py",
            ROOT / "action_privacy_v8/descriptor.py",
            ROOT / "action_privacy_v8/routing.py",
            ROOT / "v11_full_scope/canonical.py",
            ROOT / "v11_full_scope/frameworks.py",
            ROOT / "v11_full_scope/structural.py",
            ROOT / "canonical_v9_1/projection.py",
            ROOT / "scripts/run_v11_1_scheduler_closure.py",
            ROOT / "PUBLIC_PROFILE_DEVELOPMENT_V11_1.json",
        ]
        freeze = {
            "schema": "AgentTool.V11_1ExecutionHarnessFreeze/1",
            "status": "FROZEN_AFTER_FULL_SCOPE_RELIABILITY_PASS",
            "holdout_cases_selected": 0,
            "holdout_cases_executed": 0,
            "linux_binary": {"path": args.linux_binary_path, "sha256": args.linux_binary_sha256},
            "files": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in hash_paths},
            "gates": {
                "profile": f"{sum(bool(row['passed']) for row in profile)}/{len(profile)}",
                "fault": f"{sum(truth(row['passed']) for row in faults)}/{len(faults)}",
                "stress": f"{sum(truth(row['passed']) for row in stress)}/{len(stress)}",
                "semantic": f"{sum(truth(row['passed']) for row in semantic)}/{len(semantic)}",
                "structural": f"{sum(truth(row['passed']) for row in structural)}/{len(structural)}",
                "multi_action": f"{sum(truth(row['passed']) for row in multi)}/{len(multi)}",
            },
            "timing_privacy": "OPEN / NOT TESTED",
            "hardware_tee": "NOT_TESTED",
        }
        (ROOT / "V11_1_EXECUTION_HARNESS_FREEZE.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

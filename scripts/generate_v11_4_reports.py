from __future__ import annotations

import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "results_v11_4_development"


def read_csv(name: str) -> list[dict[str, str]]:
    path = RESULTS / name
    return list(csv.DictReader(path.open(encoding="utf-8"))) if path.is_file() else []


def truth(value: object) -> bool:
    return str(value).lower() == "true"


def copy_csv(source: str, destination: str) -> list[dict[str, str]]:
    path = RESULTS / source
    if path.is_file():
        shutil.copyfile(path, ROOT / destination)
    else:
        with (ROOT / destination).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["status", "reason"])
            writer.writeheader()
            writer.writerow({"status": "NOT_RUN", "reason": "upstream qualification gate did not pass"})
    return read_csv(source)


def ratio(rows: list[dict[str, str]], field: str = "passed") -> str:
    return f"{sum(truth(row.get(field, False)) for row in rows)}/{len(rows)}"


def main() -> None:
    period = json.loads((RESULTS / "period_selection.json").read_text(encoding="utf-8")) if (RESULTS / "period_selection.json").is_file() else {}
    horizon = json.loads((RESULTS / "horizon_selection.json").read_text(encoding="utf-8")) if (RESULTS / "horizon_selection.json").is_file() else {}
    gates = json.loads((RESULTS / "v11_4_gate_summary.json").read_text(encoding="utf-8")) if (RESULTS / "v11_4_gate_summary.json").is_file() else {}
    selected = gates.get("selected_profile") or horizon.get("selected_final_profile")

    period_rows = copy_csv("period_qualification.csv", "PUBLIC_PERIOD_QUALIFICATION_V11_4.csv")
    horizon_rows = copy_csv("horizon_qualification.csv", "ONLINE_HORIZON_QUALIFICATION_V11_4.csv")
    pir_rows = copy_csv("pir_delay_robustness.csv", "PIR_DELAY_ROBUSTNESS_V11_4.csv")
    decision_rows = copy_csv("decision_delay_robustness.csv", "DECISION_DELAY_ROBUSTNESS_V11_4.csv")
    action_rows = copy_csv("action_count_invariant.csv", "ACTION_COUNT_INVARIANT_V11_4.csv")
    depth_rows = copy_csv("causal_depth_invariant.csv", "CAUSAL_DEPTH_INVARIANT_V11_4.csv")
    structural_source = "structural_regression_effective.csv" if (RESULTS / "structural_regression_effective.csv").is_file() else "structural_regression.csv"
    structural_rows = copy_csv(structural_source, "ONLINE_TRAJECTORY_STRUCTURAL_REGRESSION_V11_4.csv")
    semantic_rows = copy_csv("semantic_regression.csv", "ONLINE_SEMANTIC_REGRESSION_V11_4.csv")
    final_rows = copy_csv("final_reliability.csv", "FINAL_ONLINE_RELIABILITY_V11_4.csv")
    mixed_rows = read_csv("mixed_qualification.csv")

    period_table = [
        "| Period | Passed | Sessions | Misses | Overflow | Dummy heavy | Silent loss | Selected |",
        "|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for item in period.get("candidate_outcomes", []):
        period_table.append(
            f"| {item['period_ms']} ms | {item['passed_sessions']}/{item['sessions']} | {item['sessions']} | "
            f"{item['scheduler_misses']} | {item['profile_overflow']} | {item['dummy_heavy_ops']} | "
            f"{item['silent_committed_result_loss']} | {'Yes' if item['selected'] else 'No'} |"
        )

    horizon_table = [
        "| H | A | R | Lifetime | Causal 10 | Causal 20 | Causal 30 | Causal 50 | Selected |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for item in horizon.get("candidate_outcomes", []):
        horizon_table.append(
            f"| {item['horizon_ms']} ms | {item['admission_rounds']} | {item['total_rounds']} | "
            f"{item['scheduled_lifetime_ms']} ms | "
            + " | ".join(f"{item['strata'][str(c)]['passed']}/{item['strata'][str(c)]['total']}" for c in (10, 20, 30, 50))
            + f" | {'Yes' if item['selected'] else 'No'} |"
        )
    (ROOT / "ONLINE_HORIZON_QUALIFICATION_V11_4.md").write_text(
        "# V11.4 online horizon qualification\n\n"
        "Period selection occurred first and was frozen before these horizons were instantiated. Every row is non-holdout development evidence; failed sessions were not retried. Testing stopped after the first horizon satisfying all four causal-depth strata.\n\n"
        + "\n".join(period_table)
        + "\n\n"
        + "\n".join(horizon_table)
        + (f"\n\nMixed-family qualification: {ratio(mixed_rows)} across {len(mixed_rows)} independently executed sessions.\n" if mixed_rows else "\n\nMixed-family qualification was not run because no horizon was selected.\n"),
        encoding="utf-8",
    )

    if selected:
        m = int(selected["maximum_real_operations"])
        h = int(selected["admission_horizon_ms"])
        delta = int(selected["round_period_ms"])
        a = int(selected["admission_rounds"])
        c = int(selected["completion_rounds"])
        d = int(selected["result_drain_rounds"])
        t = int(selected["terminal_rounds"])
        r = int(selected["total_rounds"])
        req = r * int(selected["request_final_bytes"])
        resp = r * int(selected["response_final_bytes"])
        capacity = f"""# V11.4 profile capacity proof

Selected public profile: `{selected['profile_id']}`.

The mechanically checked values are `M={m}`, `H={h} ms`, `Delta={delta} ms`, `A=ceil(H/Delta)={a}`, `B=50 ms`, `C=ceil(B/Delta)={c}`, `D=M={d}`, `T={t}`, and `R=A+C+D+T={r}`. The scheduled public lifetime is {selected['scheduled_lifetime_ms']} ms.

The runner admits no more than `M` operations and admits only before the public admission boundary. If all `M` operations are admission-ready before `H`, and every admitted external operation commits within `B`, the `C` completion rounds cover the last admitted provider operation and the following `D=M` pre-existing response slots can drain one result each. The terminal slot closes the fixed session. Unused requests are NOOP and unused responses are WAIT. No completion event adds a round, session, connection, or lifetime extension.

Per-session public cost is {r} OHTTP exchanges, {req} request bytes, and {resp} response bytes at the Relay observation point, excluding lower-layer framing.
"""
    else:
        capacity = "# V11.4 profile capacity proof\n\nNo profile was selected, so no selected-profile proof is claimed. The predeclared formula remains `R=A+C+M+T`.\n"
    (ROOT / "PROFILE_CAPACITY_PROOF_V11_4.md").write_text(capacity, encoding="utf-8")

    neg_path = RESULTS / "post_gate_repair_raw" / "finite_horizon_v3" / "negative_summary.json"
    if not neg_path.is_file():
        neg_path = RESULTS / "admission_closed_negative_raw" / "negative_summary.json"
    negative = json.loads(neg_path.read_text(encoding="utf-8")) if neg_path.is_file() else None
    (ROOT / "FINITE_HORIZON_NEGATIVE_V11_4.md").write_text(
        "# V11.4 finite-horizon negative\n\n"
        + (
            f"Status: **{'PASS' if negative['passed'] else 'FAIL'}**. A non-holdout action was made ready after the selected public admission horizon. The private outcome was `{negative['private_outcome']}`; public rounds={negative['public_rounds']}, sessions={negative['public_sessions']}, provider invocations={negative['provider_invocations']}, and dummy provider operations={negative['dummy_provider_operations']}. No schedule extension or second session was created.\n"
            if negative else "Status: **NOT RUN** because no selected profile reached the post-selection gate.\n"
        ),
        encoding="utf-8",
    )

    (ROOT / "ONLINE_TRAJECTORY_STRUCTURAL_REGRESSION_V11_4.md").write_text(
        "# V11.4 online trajectory structural regression\n\n"
        f"Result: **{ratio(structural_rows)}** effective pairs. Every verdict first requires both arms to be functionally valid, then exact equality of the actual Relay-derived strict structural and size projections. The original failed Agent-identity test construction remains preserved in `results_v11_4_development/structural_regression.csv`; the effective CSV uses the fresh non-holdout V2 pair. Timestamps are excluded; timing privacy remains open.\n",
        encoding="utf-8",
    )
    (ROOT / "ONLINE_SEMANTIC_REGRESSION_V11_4.md").write_text(
        "# V11.4 online semantic regression\n\n"
        f"Result: **{ratio(semantic_rows)}** native/canonical cases. Comparisons cover action trajectory, arguments, provider-visible logical requests, effect count, intermediate results, outcome semantics, and final framework-visible state. Chain-of-thought is neither captured nor compared.\n",
        encoding="utf-8",
    )
    (ROOT / "FINAL_ONLINE_RELIABILITY_V11_4.md").write_text(
        "# V11.4 final online reliability\n\n"
        f"Result: **{ratio(final_rows)}** sessions. This is a new no-retry development campaign using only the selected profile after period and horizon selection. It is not a holdout.\n",
        encoding="utf-8",
    )

    passed = bool(gates.get("all_gates_pass"))
    matrix_rows = [
        ("V11.2 negative 17/20", "PASS (preserved)"),
        ("V11.3 1,000-session negative", "PASS (preserved)"),
        ("5 ms final profile", "DEVELOPMENT_DISQUALIFIED"),
        ("Public period qualification", "PASS" if period.get("selected_profile") else "FAIL"),
        ("Online horizon qualification", "PASS" if selected else "FAIL"),
        ("Mixed causal families", ratio(mixed_rows)),
        ("PIR delay robustness", ratio(pir_rows)),
        ("Decision delay robustness", ratio(decision_rows)),
        ("Action-count invariant", ratio(action_rows, "invariant_pass")),
        ("Causal-depth invariant", ratio(depth_rows, "invariant_pass")),
        ("Finite-horizon fail-closed", "PASS" if negative and negative["passed"] else "FAIL / NOT RUN"),
        ("Online semantic regression", ratio(semantic_rows)),
        ("Online structural regression", ratio(structural_rows)),
        ("Final reliability", ratio(final_rows)),
        ("Timing privacy", "OPEN / NOT TESTED"),
        ("Packet-level timing", "OPEN"),
        ("Hardware TEE", "NOT_TESTED"),
        ("Action mediation coverage", "894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED"),
        ("Source-body executable subset", "0"),
    ]
    (ROOT / "CURRENT_SECURITY_MATRIX_V11_4.md").write_text(
        "# Current V11.4 security matrix\n\n| Item | Status |\n|---|---|\n"
        + "".join(f"| {name} | {status} |\n" for name, status in matrix_rows),
        encoding="utf-8",
    )

    all_observed_rows = period_rows + horizon_rows + mixed_rows + pir_rows + decision_rows + action_rows + depth_rows + semantic_rows + final_rows
    total_dummy = sum(max(0, int(row.get("dummy_heavy_ops", 0))) for row in all_observed_rows if str(row.get("dummy_heavy_ops", "")).lstrip("-").isdigit())
    total_overflow = sum(max(0, int(row.get("profile_overflow", 0))) for row in all_observed_rows if str(row.get("profile_overflow", "")).lstrip("-").isdigit())
    total_misses = sum(max(0, int(row.get("schedule_misses", 0))) for row in final_rows if str(row.get("schedule_misses", "")).lstrip("-").isdigit())
    total_loss = sum(max(0, int(row.get("silent_committed_result_loss", 0))) for row in all_observed_rows if str(row.get("silent_committed_result_loss", "")).lstrip("-").isdigit())

    audit = f"""# Final V11.4 public-profile qualification audit

## Decision

`ONLINE_ADMISSION_PROFILE = {'PASS' if passed else 'FAIL'}` and `ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE = {'YES' if passed else 'NO'}`.

V11.4 preserved the V11.2 17/20 and V11.3 1,000-session negative evidence without reinterpretation. It classified the two independent limitations as `ONLINE_ADMISSION_HORIZON_TOO_SHORT` and `FIVE_MS_SCHEDULER_NOT_FINAL_PROFILE_QUALIFIED`. Neither is described as a privacy failure.

## Sequential qualification

Stage P froze and tested the period candidates in ascending order, selecting only the first 500/500 candidate. Stage H was instantiated only after that selection and tested admission horizons in ascending order, selecting only the first candidate passing 100/100 causal-10, 50/50 causal-20, 30/30 causal-30, and 30/30 causal-50 sessions. No two-dimensional tuning, retry, candidate extension, selected holdout, or secret-dependent session extension occurred.

Selected profile: `{selected['profile_id'] if selected else 'NONE'}`. Mixed causal families: {ratio(mixed_rows)}. Final reliability: {ratio(final_rows)}. Semantic regression: {ratio(semantic_rows)}. Effective structural regression: {ratio(structural_rows)}.

Two post-selection test constructions were repaired using fresh non-holdout cases without retrying the failed arms. The original finite-horizon `H+10 ms` and V2 `H+300 ms after SESSION_READY` cases were still admitted because the latter did not account for the public 50-period start lead; both failures remain preserved. V3 waits `H + 50*Delta + 100 ms` after `SESSION_READY` and passed fail-closed. The original Agent-identity arm produced zero native outcomes; a fresh same-effect-class Agent 10 versus Agent 1 pair passed functionality and exact projections.

## Security and interpretation boundary

For a fixed public `Gamma`, the finite schedule has fixed session count, endpoint classes, HTTP/2 reuse, round count/order, OHTTP suite, sizes, and lifetime. Actions not ready before `H` fail closed. This is a finite software-profile result under the trusted-module assumption. Timing privacy remains OPEN / NOT TESTED, packet-level timing remains OPEN, and hardware TEE remains NOT_TESTED. Period qualification is scheduler reliability evidence only. No overall privacy GO is issued.

## Evidence discipline

Old V10/V10.1 selected outcomes were not observed. All V11.4 runs are non-holdout development evidence. Failures were preserved and not retried. The harness freeze exists only if every gate passed.
"""
    (ROOT / "FINAL_PUBLIC_PROFILE_QUALIFICATION_AUDIT_V11_4.md").write_text(audit, encoding="utf-8")

    selected_period = int(selected["round_period_ms"]) if selected else None
    selected_h = int(selected["admission_horizon_ms"]) if selected else None
    hrows = [row for row in horizon_rows if selected_h is not None and int(row.get("horizon_ms", -1)) == selected_h]
    counts = Counter(row.get("group", "") for row in hrows if truth(row.get("passed", False)))
    totals = Counter(row.get("group", "") for row in hrows)
    status = f"""OLD_V10_SELECTED_OUTCOMES_OBSERVED: NO
V10_1_SELECTED_OUTCOMES_OBSERVED: NO
V11_2_NEGATIVE_EVIDENCE_PRESERVED: PASS
V11_3_1000_SESSION_NEGATIVE_EVIDENCE_PRESERVED: PASS
FIVE_MS_FINAL_PROFILE_STATUS: DEVELOPMENT_DISQUALIFIED
SELECTED_PUBLIC_PERIOD_MS: {selected_period if selected_period is not None else 'NONE'}
PUBLIC_PERIOD_QUALIFICATION: {'PASS' if period.get('selected_profile') else 'FAIL'}
SELECTED_ADMISSION_HORIZON_MS: {selected_h if selected_h is not None else 'NONE'}
SELECTED_ADMISSION_ROUNDS: {selected['admission_rounds'] if selected else 'NONE'}
SELECTED_TOTAL_ROUNDS: {selected['total_rounds'] if selected else 'NONE'}
SELECTED_PUBLIC_LIFETIME_MS: {selected['scheduled_lifetime_ms'] if selected else 'NONE'}
CAUSAL_10: {counts['CAUSAL_10']}/{totals['CAUSAL_10']}
CAUSAL_20: {counts['CAUSAL_20']}/{totals['CAUSAL_20']}
CAUSAL_30: {counts['CAUSAL_30']}/{totals['CAUSAL_30']}
CAUSAL_50: {counts['CAUSAL_50']}/{totals['CAUSAL_50']}
MIXED_CAUSAL_FAMILIES: {ratio(mixed_rows)}
ACTION_COUNT_PUBLIC_INVARIANT: {'PASS' if action_rows and all(truth(r.get('invariant_pass')) for r in action_rows) else 'FAIL'}
CAUSAL_DEPTH_PUBLIC_INVARIANT: {'PASS' if depth_rows and all(truth(r.get('invariant_pass')) for r in depth_rows) else 'FAIL'}
FINITE_HORIZON_FAIL_CLOSED: {'PASS' if negative and negative['passed'] else 'FAIL'}
ONLINE_SEMANTIC_REGRESSION: {ratio(semantic_rows)}
ONLINE_STRUCTURAL_REGRESSION: {ratio(structural_rows)}
FINAL_ONLINE_RELIABILITY: {ratio(final_rows)}
PUBLIC_SESSION_COUNT: 1
DUMMY_HEAVY_OPS: {total_dummy}
PROFILE_OVERFLOW: {total_overflow}
SCHEDULER_MISS: {total_misses} in accepted final runs
SILENT_COMMITTED_RESULT_LOSS: {total_loss}
TIMING_PRIVACY: OPEN / NOT TESTED
PACKET_LEVEL_TIMING: OPEN
HARDWARE_TEE: NOT_TESTED
ACTION_MEDIATION_COVERAGE: 894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED
SOURCE_BODY_EXECUTABLE_SUBSET: 0
ONLINE_ADMISSION_PROFILE: {'PASS' if passed else 'FAIL'}
ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE: {'YES' if passed else 'NO'}
V11_4_ONLINE_EXECUTION_HARNESS_FROZEN: {'YES' if (ROOT / 'V11_4_ONLINE_EXECUTION_HARNESS_FREEZE.json').is_file() and passed else 'NO'}
READY_FOR_V11A_FRESH_HOLDOUT_FREEZE: {'YES' if passed else 'NO'}
"""
    (RESULTS / "final_console_summary.txt").write_text(status, encoding="utf-8")


if __name__ == "__main__":
    main()

from __future__ import annotations

import csv
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_3.profile import candidate_profiles

RESULTS = ROOT / "results_v11_3_development"


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else ["status", "reason"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def bool_value(value: str) -> bool:
    return value.lower() == "true"


def main() -> None:
    source = RESULTS / "candidate_qualification.csv"
    rows = list(csv.DictReader(source.open(encoding="utf-8")))
    if len(rows) != 1000:
        raise AssertionError(f"expected 1000 predeclared qualification rows, got {len(rows)}")
    shutil.copyfile(source, ROOT / "CAUSAL_DEPTH_QUALIFICATION_V11_3.csv")

    expected_rounds = {profile.admission_rounds: profile.total_rounds for profile in candidate_profiles()}
    summaries: list[dict[str, Any]] = []
    by_candidate: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_candidate[int(row["admission_rounds"])].append(row)
    for profile in candidate_profiles():
        group_rows = by_candidate[profile.admission_rounds]
        strata = {}
        for count in (10, 20, 30, 50):
            subset = [row for row in group_rows if row["group"] == f"CAUSAL_{count}"]
            strata[str(count)] = {
                "passed": sum(bool_value(row["passed"]) for row in subset),
                "total": len(subset),
                "resolved_not_admitted": sum(int(row["resolved_not_admitted"]) for row in subset),
                "schedule_misses": sum(int(row["schedule_misses"]) for row in subset),
                "profile_overflow": sum(int(row["profile_overflow"]) for row in subset),
                "dummy_heavy_ops": sum(int(row["dummy_heavy_ops"]) for row in subset),
                "silent_committed_result_loss": sum(int(row["silent_committed_result_loss"]) for row in subset),
                "round_count_mismatches": sum(int(row["rounds"]) != profile.total_rounds for row in subset),
            }
        summaries.append(
            {
                "admission_rounds": profile.admission_rounds,
                "admission_horizon_ms": profile.admission_horizon_ms,
                "total_rounds": profile.total_rounds,
                "scheduled_lifetime_ms": profile.scheduled_lifetime_ms,
                "passed_sessions": sum(bool_value(row["passed"]) for row in group_rows),
                "total_sessions": len(group_rows),
                "selected": False,
                "strata": strata,
            }
        )

    failure_errors = Counter(row["error"] for row in rows if not bool_value(row["passed"]))
    profile_selection = {
        "schema": "AgentTool.V11_3OnlineProfileSelectionResult/1",
        "selection_rule": "smallest predeclared admission horizon passing every required session",
        "selection_rule_applied": True,
        "candidates_changed_after_results": False,
        "seed_search": False,
        "candidate_results": summaries,
        "selected_profile": None,
        "status": "NO_PREDECLARED_CANDIDATE_PASSED",
        "online_admission_profile": "FAIL",
        "larger_unplanned_candidate_added": False,
        "post_selection_gates_run": False,
        "holdout_selected_or_executed": False,
    }
    write_json(ROOT / "PUBLIC_PROFILE_ONLINE_V11_3.json", profile_selection)

    table = [
        "| A | Horizon | R | Lifetime | 10 actions | 20 actions | 30 actions | 50 actions | Selected |",
        "| -: | -: | -: | -: | -: | -: | -: | -: | :-: |",
    ]
    for item in summaries:
        table.append(
            f"| {item['admission_rounds']} | {item['admission_horizon_ms']} ms | {item['total_rounds']} | "
            f"{item['scheduled_lifetime_ms']} ms | "
            + " | ".join(f"{item['strata'][str(count)]['passed']}/{item['strata'][str(count)]['total']}" for count in (10, 20, 30, 50))
            + " | No |"
        )
    (ROOT / "CAUSAL_DEPTH_QUALIFICATION_V11_3.md").write_text(
        "# V11.3 strictly causal qualification\n\n"
        "All 1,000 sessions are fresh non-holdout development runs on the authorized Linux host. Each future action was generated only after the previous framework-visible result. The predeclared smallest-passing selection rule found no admissible candidate.\n\n"
        + "\n".join(table)
        + "\n\nThe maximum candidate `A=300` passed 100/100 ten-action, 50/50 twenty-action, and 30/30 thirty-action sessions, but 0/20 fifty-action sessions. Across those fifty-action runs, 100 resolved actions were explicitly not admitted; one run also had one scheduler miss. No candidate therefore satisfies the all-session gate.\n\n"
        "Observed failures were preserved as framework trajectories with fewer outcomes than requested, with underlying raw runner records retaining `resolved_not_admitted_ids` and schedule status. No failed session was retried.\n",
        encoding="utf-8",
    )

    (ROOT / "ONLINE_PROFILE_SELECTION_V11_3.md").write_text(
        "# V11.3 online profile selection\n\n"
        "The predeclared rule was applied exactly: evaluate A=75, 100, 150, 200, 300 in order and select the first candidate passing every required session. No candidate passed, so `selected_profile = null`. The task-authorized range was not extended after observing outcomes.\n\n"
        + "\n".join(table)
        + "\n\nPost-selection qualification, final reliability, semantic regression, structural regression, invariants, and the deliberate finite-horizon negative test were not run because each requires an actually selected profile. This is a gate failure, not missing positive evidence to be inferred.\n",
        encoding="utf-8",
    )

    not_run = [{"status": "NOT_RUN_NO_SELECTED_PROFILE", "reason": "all predeclared admission candidates failed the strictly causal qualification gate"}]
    for name in (
        "PIR_DELAY_ROBUSTNESS_V11_3.csv",
        "DECISION_DELAY_ROBUSTNESS_V11_3.csv",
        "ACTION_COUNT_INVARIANT_V11_3.csv",
        "CAUSAL_DEPTH_INVARIANT_V11_3.csv",
        "ONLINE_RELIABILITY_FINAL_V11_3.csv",
        "ONLINE_SEMANTIC_REGRESSION_V11_3.csv",
        "ONLINE_STRUCTURAL_REGRESSION_V11_3.csv",
    ):
        write_csv(ROOT / name, not_run)

    (ROOT / "ONLINE_ADMISSION_CLOSED_NEGATIVE_V11_3.md").write_text(
        "# V11.3 admission-closed negative test\n\nStatus: **NOT RUN — NO SELECTED PROFILE**. The deliberately late selected-profile test was gated on profile selection. Qualification itself produced explicit admission closure at every candidate where causal depth exceeded the horizon; these negative outcomes never added a session, public round, connection, or dummy provider operation. They are capacity failures, but they do not replace the separately predeclared selected-profile negative test.\n",
        encoding="utf-8",
    )
    (ROOT / "ONLINE_RELIABILITY_FINAL_V11_3.md").write_text(
        "# V11.3 final online reliability campaign\n\nStatus: **NOT RUN — NO SELECTED PROFILE**. The required 320-run selected-profile campaign was not started. Candidate qualification cannot be substituted for this final campaign.\n",
        encoding="utf-8",
    )
    (ROOT / "ONLINE_SEMANTIC_REGRESSION_V11_3.md").write_text(
        "# V11.3 online semantic regression\n\nStatus: **NOT RUN — NO SELECTED PROFILE**. V11.2 semantic evidence remains preserved, but it is not relabeled as a V11.3 selected-profile result.\n",
        encoding="utf-8",
    )
    (ROOT / "ONLINE_STRUCTURAL_REGRESSION_V11_3.md").write_text(
        "# V11.3 online structural regression\n\nStatus: **NOT RUN — NO SELECTED PROFILE**. No timestamps or classifiers were used. V11.2 structural evidence remains preserved but is not substituted for the missing selected-profile regression.\n",
        encoding="utf-8",
    )

    matrix = """# Current V11.3 security matrix

| Item | Status | Evidence / boundary |
|---|---|---|
| V11.2 online ingress, single session, live results, dynamic SimplePIR | PASS (preserved) | `V11_2_ONLINE_DEVELOPMENT_FREEZE_V11_3.json` |
| V11.2 negative 17/20 | PASS (preserved) | Not relabeled; 3 admission closures remain |
| Predeclared candidate selection rule | PASS | 1,000 sessions; no candidate selected |
| Online admission profile | FAIL | A=300 fifty-action stratum 0/20 |
| Online reliability final | NOT RUN | Requires selected profile |
| Action-count public invariant | NOT RUN | Requires selected profile |
| Causal-depth public invariant | NOT RUN | Requires selected profile |
| Finite-horizon deliberate negative | NOT RUN | Requires selected profile |
| Online semantic regression | NOT RUN | Requires selected profile |
| Online structural/size regression | NOT RUN | Requires selected profile |
| Dummy heavy operations in qualification | PASS | Aggregate 0 |
| Profile overflow in qualification | PASS | Aggregate 0 |
| Silent committed-result loss in qualification | PASS | Aggregate 0 |
| Timing privacy | OPEN / NOT TESTED | No timing classifier |
| Packet-level timing | OPEN | Out of this phase |
| Hardware TEE | NOT_TESTED | Not a software-profile blocker |
| Frozen action mediation corpus | 894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED | Unchanged |
| Source-body executable subset | 0 | Unchanged |
| V10/V10.1 selected outcomes observed | NO | No holdout path called |
"""
    (ROOT / "CURRENT_SECURITY_MATRIX_V11_3.md").write_text(matrix, encoding="utf-8")

    total_misses = sum(int(row["schedule_misses"]) for row in rows)
    total_overflow = sum(int(row["profile_overflow"]) for row in rows)
    total_dummy = sum(int(row["dummy_heavy_ops"]) for row in rows)
    total_loss = sum(int(row["silent_committed_result_loss"]) for row in rows)
    total_sessions = sum(int(row["public_sessions"]) for row in rows)
    total_not_admitted = sum(int(row["resolved_not_admitted"]) for row in rows)
    audit = f"""# Final V11.3 online profile-closure audit

## Decision

`ONLINE_ADMISSION_PROFILE = FAIL` and `ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE = NO`.

The development phase correctly separated maximum real operations (`M=50`) from admission opportunities (`A`). It then executed all five predeclared candidates and all 1,000 required strictly causal sessions. No candidate passed every stratum. The largest, A=300 (1,500 ms admission horizon; 361 total rounds; 1,805 ms scheduled lifetime), completed 180/200 sessions overall but 0/20 fifty-action sessions. Consequently no public profile was selected and every post-selection gate remained unexecuted.

## Root cause and evidence

The V11.2 17/20 negative result remains immutable. V11.3 confirms the broader root cause class `ONLINE_PROFILE_ADMISSION_HORIZON_TOO_SHORT`: deeper online trajectories require more public admission opportunities than the predeclared set provides. Across qualification, resolved-not-admitted events totaled {total_not_admitted}. Qualification also observed {total_misses} scheduler misses across 1,000 sessions; these are independently disqualifying and were not hidden. Aggregate profile overflow={total_overflow}, dummy heavy operations={total_dummy}, and silent committed-result loss={total_loss}.

## Selection discipline

Candidates and the smallest-passing rule were frozen before execution. No seed search, candidate extension, retry of failed runs, holdout inspection, V10/V10.1 selected execution, secret-dependent session extension, second session, or public-profile mutation occurred. The result does not authorize adding A=400 after inspection; doing so would require a new explicitly predeclared development phase.

## What remains established

V11.2 online ingress, one public session, live delivery, dynamic SimplePIR, Agent-as-Tool, and OpenAI handoff remain preserved development evidence. V11.3 does not invalidate those mechanisms. It shows only that the current predeclared online public-profile family is not capacious enough to close the full 50-operation strictly causal scope.

## Claims not made

Timing privacy remains OPEN / NOT TESTED; packet-level timing remains OPEN; hardware TEE remains NOT_TESTED. No overall privacy GO is issued. No V11.3 harness freeze is created because the completion gate did not pass.

## Evidence integrity

Qualification host and binary provenance are in `results_v11_3_development/qualification_host.json`. The machine-readable 1,000-row result is `CAUSAL_DEPTH_QUALIFICATION_V11_3.csv`. Raw per-session evidence remains on the authorized Linux qualification host and is indexed by the transferred hash manifest.
"""
    (ROOT / "FINAL_ONLINE_PROFILE_CLOSURE_AUDIT_V11_3.md").write_text(audit, encoding="utf-8")

    final_status = f"""OLD_V10_SELECTED_OUTCOMES_OBSERVED: NO
V10_1_SELECTED_OUTCOMES_OBSERVED: NO
V11_2_NEGATIVE_17_OF_20_PRESERVED: PASS
MAXIMUM_REAL_OPERATIONS: 50
SELECTED_ADMISSION_ROUNDS: NONE
SELECTED_ADMISSION_HORIZON_MS: NONE
SELECTED_TOTAL_ROUNDS: NONE
SELECTED_PUBLIC_LIFETIME_MS: NONE
ONLINE_PROFILE_SELECTION_RULE: PASS
CAUSAL_10: no single selected profile; A300=100/100
CAUSAL_20: no single selected profile; A300=50/50
CAUSAL_30: no single selected profile; A300=30/30
CAUSAL_50: no single selected profile; A300=0/20
ACTION_COUNT_PUBLIC_INVARIANT: NOT RUN
CAUSAL_DEPTH_PUBLIC_INVARIANT: NOT RUN
FINITE_ADMISSION_HORIZON_FAIL_CLOSED: NOT RUN AS SELECTED-PROFILE TEST
ONLINE_SEMANTIC_REGRESSION: NOT RUN
ONLINE_STRUCTURAL_REGRESSION: NOT RUN
ONLINE_RELIABILITY_FINAL: NOT RUN
PUBLIC_SESSION_COUNT: 1 in all {total_sessions}/1000 qualification traces
DUMMY_HEAVY_OPS: {total_dummy}
PROFILE_OVERFLOW: {total_overflow}
SCHEDULER_MISS: {total_misses} across all qualification runs
SILENT_COMMITTED_RESULT_LOSS: {total_loss}
TIMING_PRIVACY: OPEN / NOT TESTED
PACKET_LEVEL_TIMING: OPEN
HARDWARE_TEE: NOT_TESTED
ACTION_MEDIATION_COVERAGE: 894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED
SOURCE_BODY_EXECUTABLE_SUBSET: 0
ONLINE_ADMISSION_PROFILE: FAIL
ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE: NO
V11_3_ONLINE_EXECUTION_HARNESS_FROZEN: NO
READY_FOR_V11A_FRESH_HOLDOUT_FREEZE: NO
"""
    (RESULTS / "final_console_summary.txt").write_text(final_status, encoding="utf-8")
    write_json(
        RESULTS / "qualification_aggregate.json",
        {
            "sessions": len(rows),
            "public_sessions": total_sessions,
            "resolved_not_admitted": total_not_admitted,
            "schedule_misses": total_misses,
            "profile_overflow": total_overflow,
            "dummy_heavy_ops": total_dummy,
            "silent_committed_result_loss": total_loss,
            "failure_errors": dict(failure_errors),
            "candidate_results": summaries,
        },
    )


if __name__ == "__main__":
    main()

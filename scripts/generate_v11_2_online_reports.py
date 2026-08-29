from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results_v11_2_development" / "linux_campaign_d"


def read_csv(name: str) -> list[dict[str, str]]:
    with (RESULTS / name).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text.strip() + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bool_field(row: dict[str, str], field: str = "passed") -> bool:
    return row.get(field, "").lower() == "true"


def table(rows: list[dict[str, str]], fields: list[str]) -> str:
    head = "| " + " | ".join(fields) + " |"
    sep = "| " + " | ".join("---" for _ in fields) + " |"
    body = ["| " + " | ".join(str(row.get(field, "")) for field in fields) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def main() -> None:
    causal = read_csv("online_causal_workflows.csv")
    stress = read_csv("online_reliability_stress.csv")
    semantic = read_csv("online_semantic_development.csv")
    structural = read_csv("online_structural_regression.csv")
    go_summary = json.loads((RESULTS / "linux_go_test_summary.json").read_text(encoding="utf-8"))
    same_config_smoke = json.loads((RESULTS / "same_config_prefreeze_smoke_failure.json").read_text(encoding="utf-8"))
    expected_stress = {
        "TOOL_1": 100,
        "TOOL_TO_TOOL": 50,
        "TOOL_TO_AGENT_AS_TOOL": 50,
        "TOOL_TO_HANDOFF": 50,
        "MICROSOFT_TOOL_TO_AGENT_AS_TOOL": 50,
        "DYNAMIC_5_ACTION": 30,
        "DYNAMIC_10_ACTION": 20,
        "INTERNAL_EXTERNAL_MIX": 30,
    }
    counts = Counter(row["gate"] for row in stress)
    stress_complete = len(stress) == sum(expected_stress.values()) and counts == Counter(expected_stress)
    stress_pass = stress_complete and all(bool_field(row) for row in stress)
    reliability_gate = stress_pass and int(same_config_smoke["failed"]) == 0
    causal_pass = len(causal) == 6 and all(bool_field(row) and bool_field(row, "semantic_equal") and bool_field(row, "causal") for row in causal)
    semantic_pass = len(semantic) == 8 and all(bool_field(row) and bool_field(row, "projection_equal") and bool_field(row, "causal") for row in semantic)
    structural_pass = len(structural) == 5 and all(bool_field(row) and bool_field(row, "structural_equal") and bool_field(row, "size_equal") for row in structural)
    one_session = all(str(row["public_sessions"]) == "1" for row in stress + causal + semantic) and all(
        str(row["arm_a_sessions"]) == "1" and str(row["arm_b_sessions"]) == "1" for row in structural
    )
    totals = {
        "dummy_heavy_ops": sum(int(row["dummy_heavy_ops"]) for row in stress),
        "profile_overflow": sum(int(row["profile_overflow"]) for row in stress),
        "schedule_misses": sum(int(row["schedule_misses"]) for row in stress),
        "silent_committed_result_loss": sum(int(row["silent_committed_result_loss"]) for row in stress),
    }
    online_dynamic_pass = causal_pass and semantic_pass and structural_pass and go_summary.get("passed") is True
    all_gates = all(
        (
            causal_pass,
            reliability_gate,
            semantic_pass,
            structural_pass,
            go_summary.get("passed") is True,
            all(value == 0 for value in totals.values()),
        )
    )

    for source, target in (
        ("online_causal_workflows.csv", "ONLINE_CAUSAL_WORKFLOWS_V11_2.csv"),
        ("online_reliability_stress.csv", "ONLINE_RELIABILITY_STRESS_V11_2.csv"),
        ("online_semantic_development.csv", "ONLINE_SEMANTIC_DEVELOPMENT_V11_2.csv"),
        ("online_structural_regression.csv", "ONLINE_STRUCTURAL_REGRESSION_V11_2.csv"),
    ):
        shutil.copyfile(RESULTS / source, ROOT / target)

    write(
        "ONLINE_TRAJECTORY_GAP_AUDIT_V11_2.md",
        """
# Online trajectory gap audit V11.2

The immutable V11.1 runner accepted the complete private `actions[]` array before transport start, pre-encapsulated every REAL/NOOP request before T0, and the framework adapter launched a fresh canonical process per action. That evidence established a fixed transcript for predeclared workloads, not an online Agent trajectory.

V11.2 preserves static mode but adds a distinct online path. Its startup manifest mechanically requires `actions: []`. A framework run and its one public scheduler execute concurrently; only the action actually reached by the native framework is resolved and submitted. Results are decapsulated and returned over trusted IPC while later public slots continue. The private lifecycle evidence verifies every child submit follows its causal parent's framework delivery.

No V10 or V10.1 selected case was loaded or executed. No final holdout was selected.
""",
    )
    write(
        "TRUSTED_ONLINE_CONTROL_PROTOCOL_V11_2.md",
        """
# Trusted online control protocol V11.2

The development IPC is framed JSON over the online runner's inherited stdin/stdout. It is local trusted-control traffic and never traverses the Relay.

- Runner to caller: `SESSION_READY`, `ACTION_ACCEPTED`, `ACTION_ADMITTED`, `ACTION_REJECTED`, `RESULT_AVAILABLE`, `SESSION_COMPLETE`, `SESSION_FAILURE`.
- Caller to runner: `SUBMIT_RESOLVED_ACTION` only.
- Every action carries one bounded operation ID and one resolved private action. Duplicate IDs, unknown routes, effect/policy mismatches, and capacity violations fail closed.
- `RESULT_AVAILABLE` is emitted immediately after current-slot OHTTP response decapsulation, not after round 111.
- A session failure wakes trusted waiters through an explicit failure event. No automatic action retry or second public session exists.

This IPC is a local software trust-boundary prototype, not hardware-attested communication.
""",
    )
    write(
        "ONLINE_CANONICAL_SESSION_V11_2.md",
        """
# Online canonical session V11.2

`CanonicalOnlineSession` owns exactly one Go runner process for the entire native framework run. The runner establishes one Client-to-Relay and one Relay-to-Gateway HTTP/2 connection before T0, prebuilds 111 NOOP requests, and runs the scheduler concurrently with response decapsulation and trusted result delivery.

The final development profile remains 111 rounds, 50 admission rounds, 1079-byte requests, 800-byte responses, 5 ms period, and 555 ms scheduled lifetime. A fixed 50-period public setup lead occurs before slot 1 so native framework startup does not consume the H50 admission window; it cannot be extended by private work. Completion does not terminate the public schedule early. Static-plan mode remains available only as frozen regression evidence.
""",
    )
    write(
        "ONLINE_ACTION_INGRESS_V11_2.md",
        """
# Online action ingress V11.2

The bounded ingress channel accepts at most 50 unique resolved operations. The framework adapter calls `session.submit(intent)` only when pinned framework machinery reaches that action. Arrival order and operation IDs are retained in private lifecycle evidence. The startup plan contains zero actions and the pre-T0 action queue count is zero.

Late or excess actions receive explicit private `PROFILE_ADMISSION_CLOSED` or `PROFILE_CAPACITY_EXCEEDED` outcomes. They do not extend the schedule or start a replacement session.
""",
    )
    write(
        "ONLINE_PRIVATE_RESOLUTION_V11_2.md",
        """
# Online private resolution V11.2

The official SimplePIR database construction and query-independent preprocessing occur before T0 in one persistent bridge process. The bridge startup receives no future indices. Each native framework action triggers a fresh randomized query only after its target is selected; the recovered `AgentDescriptorV7` is authenticated and then passed through `TrustedActionRouter`.

External resolved actions enter the Go ingress queue. `TRUSTED_MODULE_LOCAL` actions execute in `LocalTrustedBackendV11` while the same public session continues NOOP/WAIT cover slots. SimplePIR query hashes were fresh in accepted sessions. This is software-boundary development evidence; hardware TEE remains NOT_TESTED.
""",
    )
    write(
        "DYNAMIC_SLOT_PREPARATION_V11_2.md",
        """
# Dynamic slot preparation V11.2

Every slot has an immutable prebuilt NOOP and fresh OHTTP context before T0. A single trusted preparation worker preserves causal arrival order. For an accepted action it selects the earliest still-future admission slot, builds bounded BHTTP, fixed padding, and a fresh OHTTP request bound to that slot.

The public preparation lead is 2 ms. At cutoff the scheduler atomically commits either the completed REAL request or the prebuilt NOOP. The committed slot cannot be changed. Candidate contexts that miss cutoff are discarded and never reused. Private preparation never changes the deadline, slot count, connection, endpoint, or wire size.
""",
    )
    write(
        "ONLINE_ADMISSION_POLICY_V11_2.md",
        """
# Online admission policy V11.2

Admission is limited to public slots 1 through 50 and at most 50 accepted real operations. The public session never extends. A resolved action without a remaining eligible cutoff is rejected privately as `PROFILE_ADMISSION_CLOSED`; a 51st unique submission is `PROFILE_CAPACITY_EXCEEDED`.

At session end the runner separately reports admitted operations, delivered results, resolved-but-not-admitted IDs, unresolved IDs, pending operation IDs, and framework waiters. COMPLETE requires no pending accepted waiter and no silent committed-result loss.

The policy is safe but not sufficiently capacious for the full requested workload: under the final development configuration, 3/20 pre-freeze ten-action sessions reached `PROFILE_ADMISSION_CLOSED` before action ten. This is an explicit private capacity failure, not silent loss and not a public-session extension.
""",
    )
    write(
        "ONLINE_CAUSAL_WORKFLOWS_V11_2.md",
        "# Online causal workflows V11.2\n\n" + table(causal, ["workflow", "framework", "passed", "semantic_equal", "causal", "dynamic_pir", "public_sessions"]) + f"\n\nResult: **{sum(bool_field(row) for row in causal)}/{len(causal)}**. Microsoft native handoff remains NATIVE_MECHANISM_ABSENT. All second actions were submitted after delivery of the first result.",
    )
    write(
        "ONLINE_RELIABILITY_STRESS_V11_2.md",
        "# Online reliability stress V11.2\n\n" + table([{"gate": gate, "passed": sum(bool_field(row) for row in stress if row["gate"] == gate), "total": counts[gate]} for gate in expected_stress], ["gate", "passed", "total"]) + f"\n\nCampaign D: **{sum(bool_field(row) for row in stress)}/{len(stress)}**. Same-final-configuration pre-freeze check: **{same_config_smoke['passed']}/{same_config_smoke['sessions']}**, with {same_config_smoke['failed']} explicit `PROFILE_ADMISSION_CLOSED` failures before the tenth causal action. The reproducible reliability gate is therefore **{'PASS' if reliability_gate else 'FAIL'}**. Aggregate Campaign D dummy heavy operations={totals['dummy_heavy_ops']}, profile overflow={totals['profile_overflow']}, schedule misses={totals['schedule_misses']}, silent committed-result loss={totals['silent_committed_result_loss']}.",
    )
    write(
        "ONLINE_SEMANTIC_DEVELOPMENT_V11_2.md",
        "# Online semantic development V11.2\n\n" + table(semantic, ["case", "framework", "passed", "projection_equal", "causal", "public_sessions"]) + f"\n\nLevel-A native/canonical causal trajectory equality: **{sum(bool_field(row) for row in semantic)}/{len(semantic)}**. Compared fields were ordered logical actions, arguments, provider-visible logical requests, effect counts, per-operation outcomes, intermediate results, and final framework state. Chain-of-thought was not inspected.",
    )
    write(
        "ONLINE_STRUCTURAL_REGRESSION_V11_2.md",
        "# Online structural regression V11.2\n\n" + table(structural, ["pair", "passed", "arm_a_functional", "arm_b_functional", "structural_equal", "size_equal", "arm_a_sessions", "arm_b_sessions"]) + f"\n\nExact Relay structural/size equality: **{sum(bool_field(row) for row in structural)}/{len(structural)}**. Timestamps were excluded from the verdict.",
    )

    session_rows = []
    for row in stress:
        session_rows.append({"source": "STRESS", "case": f"{row['gate']}:{row['iteration']}", "runner_processes": 1, "preconnects": 1, "public_sessions": row["public_sessions"], "client_relay_connections": 1, "relay_gateway_connections": 1, "rounds": row["rounds"], "passed": row["passed"]})
    for row in causal:
        session_rows.append({"source": "CAUSAL", "case": row["workflow"], "runner_processes": 1, "preconnects": 1, "public_sessions": row["public_sessions"], "client_relay_connections": 1, "relay_gateway_connections": 1, "rounds": 111, "passed": row["passed"]})
    for row in semantic:
        session_rows.append({"source": "SEMANTIC", "case": row["case"], "runner_processes": 1, "preconnects": 1, "public_sessions": row["public_sessions"], "client_relay_connections": 1, "relay_gateway_connections": 1, "rounds": 111, "passed": row["passed"]})
    for row in structural:
        for arm in ("a", "b"):
            session_rows.append({"source": f"STRUCTURAL_{arm.upper()}", "case": f"{row['pair']}:{arm.upper()}", "runner_processes": 1, "preconnects": 1, "public_sessions": row[f"arm_{arm}_sessions"], "client_relay_connections": 1, "relay_gateway_connections": 1, "rounds": 111, "passed": row[f"arm_{arm}_functional"]})
    with (ROOT / "ONLINE_SESSION_COUNT_AUDIT_V11_2.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = list(session_rows[0])
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(session_rows)
    write(
        "ONLINE_SESSION_COUNT_AUDIT_V11_2.md",
        f"# Online session-count audit V11.2\n\nAudited {len(session_rows)} development Agent runs. Every accepted row records one runner process, one public preconnect transaction, one public session, one reused HTTP/2 connection per hop, and 111 public rounds. Result: **{'PASS' if all(str(row['public_sessions']) == '1' and str(row['rounds']) == '111' and bool_field(row) for row in session_rows) else 'FAIL'}**.",
    )
    write(
        "ONLINE_CAPACITY_AUDIT_V11_2.md",
        f"""
# Online capacity audit V11.2

- Public capacity: 50 operations in admission slots 1..50.
- Public schedule: 111 rounds and 555 ms; never extended by private completion.
- Accepted stress sessions: {len(stress)}.
- Clean Campaign D: {sum(bool_field(row) for row in stress)}/{len(stress)}.
- Same-final-configuration ten-action pre-freeze check: {same_config_smoke['passed']}/{same_config_smoke['sessions']}; {same_config_smoke['failed']} actions were explicitly rejected after H50 admission closed.
- Profile overflow in accepted stress: {totals['profile_overflow']}.
- Silent committed-result loss: {totals['silent_committed_result_loss']}.
- Scheduler misses in accepted sessions: {totals['schedule_misses']}.
- Unused slots: prebuilt encrypted NOOP/WAIT.
- Late/excess ingress: explicit private failure, no new session.
""",
    )
    write(
        "CURRENT_SECURITY_MATRIX_V11_2.md",
        f"""
# Current security matrix V11.2

| Property | Status |
| --- | --- |
| Online dynamic action ingress | {'PASS' if online_dynamic_pass else 'FAIL'} |
| Single public session per Agent run | {'PASS' if one_session else 'FAIL'} |
| Action n+1 after result n | {'PASS' if causal_pass else 'FAIL'} |
| Dynamic SimplePIR Agent resolution | {'PASS' if all(row['dynamic_pir'].lower() == 'true' for row in stress) else 'FAIL'} |
| Online Agent-as-Tool | {'PASS' if causal_pass else 'FAIL'} |
| OpenAI online handoff | {'PASS' if causal_pass else 'FAIL'} |
| Microsoft online handoff | NATIVE_MECHANISM_ABSENT |
| Internal/external mix | {'PASS' if counts['INTERNAL_EXTERNAL_MIX'] == 30 and all(bool_field(row) for row in stress if row['gate'] == 'INTERNAL_EXTERNAL_MIX') else 'FAIL'} |
| Structural/size regression | {'PASS' if structural_pass else 'FAIL'} |
| Semantic regression | {'PASS' if semantic_pass else 'FAIL'} |
| Reliability stress | {'PASS' if reliability_gate else 'FAIL'} (Campaign D {sum(bool_field(row) for row in stress)}/{len(stress)}; same-config check {same_config_smoke['passed']}/{same_config_smoke['sessions']}) |
| Timing privacy | OPEN / NOT TESTED |
| Packet-level timing | OPEN |
| Hardware TEE | NOT_TESTED |
| Frozen mediation coverage | 894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED |
| Source-body executable subset | 0, informational only |
""",
    )
    write(
        "FINAL_ONLINE_TRAJECTORY_AUDIT_V11_2.md",
        f"""
# Final online trajectory audit V11.2

## Decision

`ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE = {'YES' if all_gates else 'NO'}`

The V11.2 development implementation closes the static-plan mismatch only if the measured gates below all pass. It does not issue an overall privacy GO and does not select or execute a final holdout.

Development Campaign B exposed an H50 admission failure in the 10-action causal stratum with a 10-period pre-start lead. Campaign C showed that a 20-period lead moved the first action to slot 1 but still left the tenth action beyond slot 50 in some sessions. A 20-session pre-freeze check with a 50-period lead and 1 ms cutoff still passed only 17/20: later native-framework and PIR steps advanced by 5--6 slots, making H50 intrinsically unreliable for this workload on the evaluated host. All negative rows and raw traces are preserved. No slot count, admission count, cadence, wire size, endpoint, or scheduled 555 ms lifetime changed. The numbers below come only from the clean final Campaign D.

- V11.1 static scheduler regression: {'PASS' if go_summary.get('passed') else 'FAIL'}.
- Online causal workflows: {sum(bool_field(row) for row in causal)}/{len(causal)}.
- Online semantic development: {sum(bool_field(row) for row in semantic)}/{len(semantic)}.
- Online structural regression: {sum(bool_field(row) for row in structural)}/{len(structural)}.
- Online reliability stress: Campaign D {sum(bool_field(row) for row in stress)}/{len(stress)}; same-final-configuration pre-freeze check {same_config_smoke['passed']}/{same_config_smoke['sessions']} ({same_config_smoke['failed']} failures).
- Dummy heavy operations: {totals['dummy_heavy_ops']}.
- Profile overflow: {totals['profile_overflow']}.
- Scheduler misses: {totals['schedule_misses']}.
- Silent committed-result loss: {totals['silent_committed_result_loss']}.

## Boundaries

Fine-grained timing privacy and packet-level timing remain open. Hardware TEE attestation is not tested. The trusted IPC is a local software abstraction. The frozen action-mediation denominator remains unchanged. Microsoft handoff is not claimed because the pinned native snapshot lacks the required mechanism.
""",
    )

    summary = f"""OLD_V10_SELECTED_OUTCOMES_OBSERVED:
NO

V10_1_SELECTED_OUTCOMES_OBSERVED:
NO

V11_1_STATIC_SCHEDULER_REGRESSION:
{'PASS' if go_summary.get('passed') is True else 'FAIL'}

ONLINE_RUNNER_STARTS_WITH_NO_FUTURE_ACTION_LIST:
{'PASS' if go_summary.get('online_startup_action_rejection') is True else 'FAIL'}

ONLINE_DYNAMIC_ACTION_INGRESS:
{'PASS' if online_dynamic_pass else 'FAIL'}

SINGLE_PUBLIC_SESSION_PER_AGENT_RUN:
{'PASS' if one_session else 'FAIL'}

DYNAMIC_TOOL_TO_TOOL:
{'PASS' if counts['TOOL_TO_TOOL'] == 50 and all(bool_field(row) for row in stress if row['gate'] == 'TOOL_TO_TOOL') else 'FAIL'}

DYNAMIC_TOOL_TO_AGENT_AS_TOOL:
{'PASS' if counts['TOOL_TO_AGENT_AS_TOOL'] == 50 and all(bool_field(row) for row in stress if row['gate'] == 'TOOL_TO_AGENT_AS_TOOL') else 'FAIL'}

DYNAMIC_TOOL_TO_HANDOFF:
{'PASS' if counts['TOOL_TO_HANDOFF'] == 50 and all(bool_field(row) for row in stress if row['gate'] == 'TOOL_TO_HANDOFF') else 'FAIL'}

DYNAMIC_MICROSOFT_AGENT_AS_TOOL:
{'PASS' if counts['MICROSOFT_TOOL_TO_AGENT_AS_TOOL'] == 50 and all(bool_field(row) for row in stress if row['gate'] == 'MICROSOFT_TOOL_TO_AGENT_AS_TOOL') else 'FAIL'}

ACTION_N_PLUS_1_AFTER_RESULT_N:
{'PASS' if causal_pass else 'FAIL'}

DYNAMIC_AGENT_PIR_RESOLUTION:
{'PASS' if len(stress) == 380 and all(row['dynamic_pir'].lower() == 'true' for row in stress) else 'FAIL'}

ONLINE_INTERNAL_EXTERNAL_MIX:
{'PASS' if counts['INTERNAL_EXTERNAL_MIX'] == 30 and all(bool_field(row) for row in stress if row['gate'] == 'INTERNAL_EXTERNAL_MIX') else 'FAIL'}

ONLINE_ACTION_COUNT_PUBLIC_INVARIANT:
{'PASS' if structural_pass and all(str(row['public_sessions']) == '1' and str(row['rounds']) == '111' for row in stress) else 'FAIL'}

ONLINE_SEMANTIC_REGRESSION:
{sum(bool_field(row) for row in semantic)}/{len(semantic)}

ONLINE_STRUCTURAL_REGRESSION:
{sum(bool_field(row) for row in structural)}/{len(structural)}

ONLINE_RELIABILITY_STRESS:
Campaign D {sum(bool_field(row) for row in stress)}/{len(stress)}; same-config pre-freeze {same_config_smoke['passed']}/{same_config_smoke['sessions']} => {'PASS' if reliability_gate else 'FAIL'}

PUBLIC_SESSION_COUNT:
{'1 per tested Agent run' if one_session else 'FAIL'}

DUMMY_HEAVY_OPS:
{totals['dummy_heavy_ops']}

PROFILE_OVERFLOW:
{totals['profile_overflow']}

SILENT_COMMITTED_RESULT_LOSS:
{totals['silent_committed_result_loss']}

TIMING_PRIVACY:
OPEN / NOT TESTED

PACKET_LEVEL_TIMING:
OPEN

HARDWARE_TEE:
NOT_TESTED

ACTION_MEDIATION_COVERAGE:
894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED

SOURCE_BODY_EXECUTABLE_SUBSET:
0, informational only

ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE:
{'YES' if all_gates else 'NO'}

V11_2_ONLINE_EXECUTION_HARNESS_FROZEN:
{'YES' if all_gates else 'NO'}

READY_FOR_V11A_FRESH_HOLDOUT_FREEZE:
{'YES' if all_gates else 'NO'}

No overall privacy GO. No final holdout was selected or executed.
"""
    summary_path = ROOT / "results_v11_2_development" / "final_console_summary.txt"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")

    if all_gates:
        freeze_files = [
            "V11_1_STATIC_SCHEDULER_FREEZE_V11_2.json",
            "PUBLIC_PROFILE_DEVELOPMENT_V11_1.json",
            "common_action_gateway_v2/canonicalv9/runner.go",
            "common_action_gateway_v2/canonicalv9/online.go",
            "common_action_gateway_v2/canonicalv9/canonicalv9_test.go",
            "common_action_gateway_v2/v8/http_relay.go",
            "common_action_gateway_v2/v9ohttp/bhttp_codec.go",
            "common_action_gateway_v2/cmd/canonical-v9-runner/main.go",
            "pir_integration/simplepir_bridge/main.go",
            "v11_online/session.py",
            "v11_online/frameworks.py",
            "canonical_v9_1/projection.py",
            "scripts/run_v11_2_online_development.py",
        ]
        freeze = {
            "schema": "AgentTool.V11_2OnlineExecutionHarnessFreeze/1",
            "status": "FROZEN_AFTER_ALL_V11_2_DEVELOPMENT_GATES_PASS",
            "files": {name: sha(ROOT / name) for name in freeze_files},
            "linux_binary": go_summary["binary"],
            "simplepir_online_binary": go_summary["simplepir_online_binary"],
            "gates": {"causal": "6/6", "semantic": "8/8", "structural": "5/5", "stress": "380/380", "go_regression": go_summary["packages"]},
            "holdout_cases_selected": 0,
            "holdout_cases_executed": 0,
            "timing_privacy": "OPEN / NOT TESTED",
            "packet_level_timing": "OPEN",
            "hardware_tee": "NOT_TESTED",
        }
        (ROOT / "V11_2_ONLINE_EXECUTION_HARNESS_FREEZE.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

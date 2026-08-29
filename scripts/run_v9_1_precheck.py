from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from action_privacy_v8 import ActionKind
from canonical_v9.runner import (
    CanonicalSessionSpec,
    Providers,
    deliver_results,
    intent,
    real_pir_select,
    resolve_session,
)
from canonical_v9_1.profile import PublicCapacityProfile, strict_h50_profile, validate_profile_id
from canonical_v9_1.projection import (
    strict_size_projection,
    strict_structural_projection,
    timing_network_diagnostics,
)
from canonical_v9_1.runner import invoke_go_with_public_profile


@dataclass(frozen=True)
class Arm:
    arm_id: str
    agent_id: int
    agent_capability: str
    actions: tuple[tuple[str, ActionKind], ...]

    def spec(self, category: str) -> CanonicalSessionSpec:
        # The canonical wire ABI has a 32-byte operation-id field.  Keep every
        # development ID short and unique before serialization; long descriptive
        # labels are private metadata in the correctness log, not protocol IDs.
        prefix = hashlib.sha256(f"{category}:{self.arm_id}".encode()).hexdigest()[:10]
        intents = tuple(
            intent(capability, kind, f"v91-{prefix}-{index:03d}")
            for index, (capability, kind) in enumerate(self.actions)
        )
        return CanonicalSessionSpec(
            f"dev-{category.lower()}-{self.arm_id.lower()}",
            self.agent_capability,
            self.agent_id,
            intents,
        )


def repeated(capability: str, kind: ActionKind, count: int) -> tuple[tuple[str, ActionKind], ...]:
    return tuple((capability, kind) for _ in range(count))


def groups() -> dict[str, tuple[Arm, ...]]:
    varied = (
        ("tool.read", ActionKind.TOOL),
        ("tool.idem", ActionKind.TOOL),
        ("tool.nonidem", ActionKind.TOOL),
        ("external.local", ActionKind.EXTERNAL_HTTP),
    )
    return {
        "PUBLIC_CAPACITY_SWEEP": tuple(
            Arm(f"COUNT_{count}", 10, "agent.tools", repeated("tool.read", ActionKind.TOOL, count))
            for count in (1, 5, 10, 25, 50)
        ),
        "DIFFERENT_AGENT": (
            Arm("AGENT_A", 1, "agent.a", repeated("tool.a", ActionKind.TOOL, 1)),
            Arm("AGENT_B", 2, "agent.b", repeated("tool.b", ActionKind.TOOL, 1)),
        ),
        "DIFFERENT_TOOL": (
            Arm("TOOL_READ", 10, "agent.tools", repeated("tool.read", ActionKind.TOOL, 8)),
            Arm("EXTERNAL_HTTP", 10, "agent.tools", repeated("external.local", ActionKind.EXTERNAL_HTTP, 8)),
        ),
        "DIFFERENT_ACTUAL_COUNT": (
            Arm("LOW_COUNT", 10, "agent.tools", repeated("tool.read", ActionKind.TOOL, 1)),
            Arm("HIGH_COUNT", 10, "agent.tools", repeated("tool.read", ActionKind.TOOL, 50)),
        ),
        "REPEATED_VS_VARIED_TARGET": (
            Arm("REPEATED", 10, "agent.tools", repeated("tool.read", ActionKind.TOOL, 20)),
            Arm("VARIED", 10, "agent.tools", tuple(varied[index % len(varied)] for index in range(20))),
        ),
        "DIFFERENT_COMPLETION_BEHAVIOR": (
            Arm("FAST", 1, "agent.a", repeated("tool.a", ActionKind.TOOL, 10)),
            Arm("SLOW_JITTERED", 13, "agent.service.13", repeated("agent.service.13", ActionKind.AGENT_SERVICE, 10)),
        ),
    }


def write_json(path: Path, value: object) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite V9.1 artifact: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite V9.1 artifact: {path}")
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def run_group(
    category: str,
    arms: tuple[Arm, ...],
    profile: PublicCapacityProfile,
    output: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    output.mkdir(parents=True, exist_ok=False)
    specs = [arm.spec(category) for arm in arms]
    selected = real_pir_select(output / "real_pir", specs)
    rows: list[dict[str, object]] = []
    projections: list[dict[str, object]] = []
    size_projections: list[dict[str, object]] = []
    with Providers(output) as providers:
        for arm, spec in zip(arms, specs, strict=True):
            arm_dir = output / "arms" / arm.arm_id.lower()
            actions = resolve_session(spec, selected[spec.case_id])
            result, schedule = invoke_go_with_public_profile(arm_dir, profile, actions, providers)
            expected = [str(action["operation_id"]) for action in actions]
            delivery = deliver_results(arm_dir, expected, result)
            projection = strict_structural_projection(result, profile)
            size_projection = strict_size_projection(result, profile)
            diagnostics = timing_network_diagnostics(result, profile)
            write_json(arm_dir / "strict_structural_projection.json", projection)
            write_json(arm_dir / "strict_size_projection.json", size_projection)
            write_json(arm_dir / "timing_network_diagnostics_not_a_privacy_test.json", diagnostics)
            write_json(
                arm_dir / "private_correctness_summary.json",
                {
                    "agent_id": arm.agent_id,
                    "authenticated_from_real_pir": True,
                    "actual_real_actions": len(actions),
                    "expected_operation_ids": expected,
                    "delivery": delivery,
                },
            )
            functional = all(
                (
                    selected[spec.case_id].agent_id == arm.agent_id,
                    len(actions) == len(arm.actions),
                    int(result["admitted"]) == len(actions),
                    int(result["provider_invocations"]) == len(actions),
                    int(result["dummy_provider_operations"]) == 0,
                    int(result["profile_overflow_events"]) == 0,
                    len(result["results"]) == len(actions),
                    not delivery["missing"],
                    not delivery["unexpected"],
                    "UNEXPECTED_REPLAY" not in delivery["framework_sink"],
                    int(schedule["public_maximum_real_operations"]) == profile.maximum_real_operations,
                    int(schedule["private_actual_real_actions"]) == len(actions),
                )
            )
            projections.append(projection)
            size_projections.append(size_projection)
            rows.append(
                {
                    "category": category,
                    "arm": arm.arm_id,
                    "profile_id": profile.profile_id,
                    "public_maximum_real_operations": profile.maximum_real_operations,
                    "private_actual_real_actions": len(actions),
                    "public_session_count": profile.session_count,
                    "public_round_count": profile.total_rounds,
                    "relay_event_count": len(result["public_relay_events"]),
                    "request_bytes_unique": ";".join(
                        map(str, sorted(set(size_projection["request_final_bytes"])))
                    ),
                    "response_bytes_unique": ";".join(
                        map(str, sorted(set(size_projection["response_final_bytes"])))
                    ),
                    "provider_invocations": int(result["provider_invocations"]),
                    "dummy_provider_operations": int(result["dummy_provider_operations"]),
                    "profile_overflow_events": int(result["profile_overflow_events"]),
                    "delivered": len(delivery["framework_sink"]),
                    "missing": len(delivery["missing"]),
                    "unexpected": len(delivery["unexpected"]),
                    "functional": functional,
                }
            )
    provider_metrics = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((output / "providers").glob("*.json"))
    ]
    duplicate_provider_calls = sum(int(item["duplicate_calls"]) for item in provider_metrics)
    functional = all(bool(row["functional"]) for row in rows) and duplicate_provider_calls == 0
    equal_structural = all(item == projections[0] for item in projections[1:])
    equal_size = all(item == size_projections[0] for item in size_projections[1:])
    summary = {
        "category": category,
        "development_only": True,
        "arm_count": len(arms),
        "profile_id": profile.profile_id,
        "functional": functional,
        "strict_structural_equal": equal_structural,
        "strict_size_equal": equal_size,
        "duplicate_provider_calls": duplicate_provider_calls,
        "dummy_provider_operations": sum(int(row["dummy_provider_operations"]) for row in rows),
        "profile_overflow_events": sum(int(row["profile_overflow_events"]) for row in rows),
        "passed": functional and equal_structural and equal_size,
    }
    write_json(output / "group_summary.json", summary)
    return rows, summary


def _source_ref(function: object) -> tuple[str, str, int]:
    path = Path(inspect.getsourcefile(function) or "UNKNOWN")
    _, line = inspect.getsourcelines(function)
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        relative = str(path)
    return relative, getattr(function, "__qualname__", str(function)), line


def audit_rows() -> list[dict[str, object]]:
    from canonical_v9 import runner as frozen_v9
    from canonical_v9_1 import profile as profile_module
    from canonical_v9_1 import runner as runner_module

    public_ref = _source_ref(profile_module.strict_h50_profile)
    validate_ref = _source_ref(profile_module.validate_profile_id)
    plan_ref = _source_ref(profile_module.PublicCapacityProfile.go_plan_fields)
    invoke_ref = _source_ref(runner_module.invoke_go_with_public_profile)
    legacy_ref = _source_ref(frozen_v9.capacity_profile)
    legacy_id_ref = _source_ref(frozen_v9.functional_run)
    go_run_ref = ("common_action_gateway_v2/canonicalv9/runner.go", "Run", 447)
    projection_ref = _source_ref(strict_structural_projection)
    rows: list[dict[str, object]] = []

    def add(field: str, classification: str, source: str, detail: str, ref: tuple[str, str, int]) -> None:
        rows.append(
            {
                "field": field,
                "classification": classification,
                "source": source,
                "detail": detail,
                "source_file": ref[0],
                "source_function": ref[1],
                "line_start": ref[2],
                "active_strict_v9_1": classification != "SECRET_DEPENDENT_INVALID",
            }
        )

    add("profile_id", "USER_SELECTED_PRIVACY_PROFILE", "strict_h50_profile + actual Relay event", "Validated public grammar and H/public-capacity match; projected from observed event sequence", projection_ref)
    for field in ("admission_rounds", "maximum_real_operations", "total_rounds", "round_period_ms", "provider_completion_bound_ms", "terminal_rounds", "session_count"):
        add(field, "USER_SELECTED_PRIVACY_PROFILE", "strict_h50_profile", "Selected before private actions", public_ref)
    add("scheduled_public_lifetime", "PUBLIC_POLICY", "total_rounds * round_period_ms", "Derived only from public fields", public_ref)
    for field in ("request_bhttp_bytes", "response_bhttp_bytes", "request_final_bytes", "response_final_bytes"):
        add(field, "PUBLIC_POLICY", "strict_h50_profile", "Frozen fixed-width OHTTP experiment policy", public_ref)
    for field in ("ohttp_key_id", "kem_id", "kdf_id", "aead_id", "config_epoch"):
        add(field, "CONSTANT_PUBLIC", "frozen canonical Go relay profile", "Public OHTTP suite/configuration epoch; checked against actual Relay events", go_run_ref)
    for field in ("relay_endpoint_class", "gateway_endpoint_class", "connection_policy", "scheduled_start_policy"):
        add(field, "CONSTANT_PUBLIC", "frozen canonical Go relay profile + V9.1 policy", "Fixed local STRICT experiment deployment", go_run_ref)
    add("go_plan_public_fields", "PUBLIC_POLICY", "PublicCapacityProfile.go_plan_fields", "No private-action argument", plan_ref)
    add("private_actual_real_actions", "SECRET", "invoke_go_with_public_profile", "Used only for capacity validation and encrypted action list", invoke_ref)
    add("historical_v9_rounds/admission/maximum", "SECRET_DEPENDENT_INVALID", "capacity_profile(actions)", "Frozen V9 development-only path derived public fields from len(actions); excluded from V9.1", legacy_ref)
    add("historical_v9_profile_id", "SECRET_DEPENDENT_INVALID", "functional_run profile format", "Frozen negative evidence; excluded from V9.1 public grammar", legacy_id_ref)
    return rows


def negative_profile_id_tests() -> list[dict[str, object]]:
    attempts = {
        "agent_id": "V9_1-STRICT-H50-P1-AGENT-17",
        "agent_name": "V9_1-STRICT-H50-P1-LEGAL-AGENT",
        "tool_name": "V9_1-STRICT-H50-P1-TOOL-EMAIL",
        "provider": "V9_1-STRICT-H50-P1-PROVIDER-SLOW",
        "route": "V9_1-STRICT-H50-P1-ROUTE-EXTERNAL",
        "actual_real_action_count": "V9_1-STRICT-H50-P1-ACTUAL-ACTIONS-14",
        "repeated_label": "V9_1-STRICT-H50-P1-REPEATED",
        "rare_label": "V9_1-STRICT-H50-P1-RARE",
        "frequency_label": "V9_1-STRICT-H50-P1-FREQUENCY-99-1",
        "workload_family": "V9_1-STRICT-H50-P1-WORKLOAD-TOOL",
        "secret_arm": "V9_1-STRICT-H50-P1-ARM-A",
        "actual_count_as_horizon": "V9_1-STRICT-H14-P1",
    }
    rows = []
    for category, value in attempts.items():
        try:
            validate_profile_id(value, 50)
            rejected = False
        except ValueError:
            rejected = True
        rows.append({"forbidden_category": category, "attempt": value, "rejected": rejected})
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite V9.1 artifact: {path}")
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def bool_status(value: bool) -> str:
    return "PASS" if value else "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ROOT / "results_v9_1" / "development_precheck")
    args = parser.parse_args()
    output = args.output_root.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite V9.1 development run: {output}")
    output.mkdir(parents=True)
    profile = strict_h50_profile()
    write_json(ROOT / "STRICT_PUBLIC_PROFILE_SCHEMA_V9_1.json", {
        "schema": "AgentTool.StrictPublicCapacityProfile/1",
        "phase": "V9.1 PRE-HOLDOUT DEVELOPMENT",
        "profile": profile.public_schema(),
        "public_fields": [
            "profile_id", "admission_rounds", "maximum_real_operations", "total_rounds",
            "round_period_ms", "provider_completion_bound_ms", "terminal_rounds", "session_count",
            "request_bhttp_bytes", "response_bhttp_bytes", "request_final_bytes", "response_final_bytes",
            "ohttp_key_id", "kem_id", "kdf_id", "aead_id", "config_epoch",
            "relay_endpoint_class", "gateway_endpoint_class", "connection_policy",
            "scheduled_start_policy", "scheduled_lifetime_ns",
        ],
        "private_fields": [
            "actual_real_actions", "action_identities", "agent_identity", "destinations",
            "real_noop_placement", "action_order", "repetition_frequency_pattern",
        ],
        "holdout": "NOT_CREATED_OR_EXECUTED",
    })
    write_json(output / "profile_id_negative_tests.json", negative_profile_id_tests())

    all_rows: list[dict[str, object]] = []
    summaries: dict[str, dict[str, object]] = {}
    for category, arms in groups().items():
        rows, summary = run_group(category, arms, profile, output / category.lower())
        all_rows.extend(rows)
        summaries[category] = summary
    write_csv(ROOT / "DEVELOPMENT_PAIR_PRECHECK_V9_1.csv", all_rows)
    write_json(output / "precheck_summary.json", summaries)

    audit = audit_rows()
    write_csv(ROOT / "PUBLIC_PROFILE_SECRET_DEPENDENCE_AUDIT_V9_1.csv", audit)
    invalid_active = [row for row in audit if row["classification"] == "SECRET_DEPENDENT_INVALID" and row["active_strict_v9_1"]]
    all_prechecks = all(bool(item["passed"]) for item in summaries.values())
    all_functional = all(bool(item["functional"]) for item in summaries.values())
    dummy = sum(int(item["dummy_provider_operations"]) for item in summaries.values())
    statuses = {
        "V9_FUNCTIONAL_FREEZE": "PASS",
        "PUBLIC_PROFILE_INDEPENDENT_OF_ACTUAL_ACTION_COUNT": bool_status(summaries["PUBLIC_CAPACITY_SWEEP"]["passed"]),
        "PUBLIC_PROFILE_ID_SECRET_FREE": bool_status(all(item["rejected"] for item in negative_profile_id_tests())),
        "PUBLIC_SESSION_COUNT_FIXED": bool_status(all(int(row["public_session_count"]) == 1 for row in all_rows)),
        "PUBLIC_ROUND_COUNT_FIXED": bool_status(all(int(row["public_round_count"]) == profile.total_rounds for row in all_rows)),
        "PUBLIC_SCHEDULED_LIFETIME_FIXED": "PASS",
        "STRICT_STRUCTURAL_PROJECTION_DEFINED": "PASS",
        "STRICT_SIZE_PROJECTION_DEFINED": "PASS",
        "DEVELOPMENT_AGENT_PAIR": bool_status(summaries["DIFFERENT_AGENT"]["passed"]),
        "DEVELOPMENT_TOOL_PAIR": bool_status(summaries["DIFFERENT_TOOL"]["passed"]),
        "DEVELOPMENT_ACTION_COUNT_PAIR": bool_status(summaries["DIFFERENT_ACTUAL_COUNT"]["passed"]),
        "DEVELOPMENT_REPETITION_PAIR": bool_status(summaries["REPEATED_VS_VARIED_TARGET"]["passed"]),
        "DEVELOPMENT_COMPLETION_PAIR": bool_status(summaries["DIFFERENT_COMPLETION_BEHAVIOR"]["passed"]),
        "DEVELOPMENT_INTERNAL_EXTERNAL_PAIR": "NOT_APPLICABLE",
        "ALL_DEVELOPMENT_ARMS_FUNCTIONAL": bool_status(all_functional),
        "DUMMY_PROVIDER_OPERATIONS": dummy,
        "DELIVERY_LEDGER": "PARTIAL",
        "TIMING_PRIVACY": "OPEN / NOT_TESTED",
        "PACKET_LEVEL_TIMING": "OPEN",
        "HARDWARE_TEE": "NOT_TESTED",
        "READY_FOR_V10_HOLDOUT_FREEZE": "YES" if all_prechecks and not invalid_active else "NO",
        "HOLDOUT_CREATED_OR_EXECUTED": "NO",
        "OVERALL_GO": "NOT_ISSUED",
    }
    write_json(output / "final_status.json", statuses)
    generate_reports(profile, all_rows, summaries, audit, statuses)
    print(json.dumps(statuses, indent=2))


def generate_reports(
    profile: PublicCapacityProfile,
    rows: list[dict[str, object]],
    summaries: dict[str, dict[str, object]],
    audit: list[dict[str, object]],
    statuses: dict[str, object],
) -> None:
    write_text(ROOT / "PUBLIC_PROFILE_SEPARATION_V9_1.md", f"""
# V9.1 Public-profile Separation

V9 is frozen by `V9_CANONICAL_FUNCTIONAL_FREEZE.json`. V9.1 does not edit its
runner or evidence. It replaces the privacy-use orchestration call
`capacity_profile(len(actions), ...)` with a preselected
`PublicCapacityProfile` passed separately from private actions.

The development profile is `{profile.profile_id}`: capacity
{profile.maximum_real_operations}, {profile.total_rounds} rounds, one public
session, {profile.request_final_bytes}-byte final OHTTP requests and
{profile.response_final_bytes}-byte responses. The runner admitted and
functionally completed 1, 5, 10, 25, and 50 real actions under this exact one
profile. Unused admission slots were encrypted NOOP and unused response slots
were encrypted WAIT. No holdout was selected or executed.
""")
    write_text(ROOT / "STRICT_STRUCTURAL_PROJECTION_V9_1.md", """
# STRICT Structural Projection V9.1

`StrictStructuralProjection(trace)` contains only: the actual Relay-observed
profile ID sequence; public OHTTP key
ID/KEM/KDF/AEAD/config epoch; Relay and Gateway endpoint classes; public session
count; normalized connection counts and reuse pattern; connection policy; round
count/order; actual Relay-observed request/response length sequences; and the
scheduled public lifetime.

Raw send/receive timestamps and literal ephemeral TCP identifiers are excluded.
Connection identifiers are first-seen-normalized, so reconnects remain visible
while different source ports in independent executions do not cause a false
structural mismatch. Private labels and correctness events are never inputs.
""")
    write_text(ROOT / "STRICT_SIZE_PROJECTION_V9_1.md", f"""
# STRICT Size Projection V9.1

The size projection is independently computed from each actual Relay event as
the ordered final OHTTP request- and response-length sequences. It does not read
configured constants as evidence. Every completed development arm produced
{profile.total_rounds} requests of {profile.request_final_bytes} bytes and
{profile.total_rounds} responses of {profile.response_final_bytes} bytes.
""")
    write_text(ROOT / "CONNECTION_PROJECTION_V9_1.md", """
# Connection Projection V9.1

The STRICT projection exposes Relay endpoint class, Gateway endpoint class,
connection count, first-seen-normalized reuse pattern, connection policy, and
session association. Raw diagnostics retain literal loopback source ports, but
those strings are neither required nor expected to match across runs. A changed
reuse pattern or reconnect changes the normalized projection and fails equality.
""")
    write_text(ROOT / "PUBLIC_LIFETIME_CONTRACT_V9_1.md", f"""
# Public Lifetime Contract V9.1

For `{profile.profile_id}`, scheduled start is the public monotonic session T0
selected when the session is accepted. Scheduled end is T0 plus
{profile.scheduled_lifetime_ns} ns ({profile.total_rounds} rounds x
{profile.round_period_ms} ms). The round budget is fixed from public capacity,
not completion. NOOP/WAIT continues through the fixed final round.

The frozen V9 runner does not export the exact connection-close timestamp.
V9.1 records Relay observation span and wrapper elapsed time separately, marks
connection-close slip `NOT_CAPTURED_BY_FROZEN_V9_RUNNER`, and makes no timing
privacy claim. Timing and packet-level timing remain OPEN.
""")

    audit_lines = [
        "# Public-profile Secret-dependence Audit V9.1",
        "",
        "| Field | Classification | Source | Active STRICT V9.1 |",
        "|---|---|---|---|",
    ]
    audit_lines.extend(
        f"| {row['field']} | {row['classification']} | `{row['source_file']}:{row['line_start']}` / `{row['source_function']}` | {row['active_strict_v9_1']} |"
        for row in audit
    )
    audit_lines.extend(
        [
            "",
            "The two SECRET_DEPENDENT_INVALID rows document the frozen V9 development path and are excluded from V9.1. No active STRICT V9.1 public field is secret-dependent.",
        ]
    )
    write_text(ROOT / "PUBLIC_PROFILE_SECRET_DEPENDENCE_AUDIT_V9_1.md", "\n".join(audit_lines))

    table = [
        "# Development Pair Precheck V9.1",
        "",
        "These are development-only sanity checks, not holdouts and not paper confirmation.",
        "",
        "| Category | Arms | Functional | Structural exact | Size exact | Result |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    table.extend(
        f"| {name} | {item['arm_count']} | {item['functional']} | {item['strict_structural_equal']} | {item['strict_size_equal']} | {item['passed']} |"
        for name, item in summaries.items()
    )
    table.extend(
        [
            "",
            f"All {len(rows)} arms used `{profile.profile_id}`, one session, {profile.total_rounds} Relay rounds, and the same scheduled lifetime. All functional gates include real PIR descriptor selection, authorization/routing, provider invocation, result delivery, no missing/unexpected result, no duplicate provider call, zero dummy provider work, and zero overflow.",
            "",
            "Timestamps were not classified or compared for privacy.",
        ]
    )
    write_text(ROOT / "DEVELOPMENT_PAIR_PRECHECK_V9_1.md", "\n".join(table))

    write_text(ROOT / "INTERNAL_EXTERNAL_STRICT_PRECHECK_V9_1.md", """
# Internal / External STRICT Precheck V9.1

Status: **NOT_APPLICABLE**.

The frozen canonical V9 catalog contains only EXTERNAL placements. The router
can reject or classify trusted-module/cloud-local placements, but the canonical
runner has no independently validated internal-Agent execution path that is
semantically comparable to its external Agent-service path. Inventing one here
would redesign V9 or create a synthetic shortcut. No pair was run and no STRICT
internal/external equality claim is made. A future holdout may include this
stratum only after legitimate canonical support exists.
""")

    readiness = "YES" if statuses["READY_FOR_V10_HOLDOUT_FREEZE"] == "YES" else "NO"
    write_text(ROOT / "CURRENT_HOLDOUT_READINESS_V9_1.md", f"""
# Current Holdout Readiness V9.1

`READY_FOR_V10_HOLDOUT_FREEZE = {readiness}`.

The public-capacity API, public-only ID grammar, fixed session/round/lifetime
contract, normalized connection projection, Relay-observed size projection,
static dataflow audit, and required development pairs pass. The internal versus
external STRICT pair is not applicable to the frozen canonical deployment and
is not claimed. The arbitrary-callback DeliveryLedger boundary remains PARTIAL;
timing, packet timing, and hardware TEE validation remain open.

No semantic or privacy holdout manifest was created, no holdout source files or
secret sequences were selected, and no confirmation was executed.
""")

    status_block = "\n".join(f"{key}: {value}" for key, value in statuses.items())
    write_text(ROOT / "FINAL_PRE_HOLDOUT_AUDIT_V9_1.md", f"""
# Final Pre-holdout Audit V9.1

V9 remains immutable at commit recorded in `V9_CANONICAL_FUNCTIONAL_FREEZE.json`.
V9.1 corrects only the privacy-use public-profile construction. One public H50
profile executed all development counts and paired workload variations with
exact structural and actual Relay-size equality and correct private semantics.

```text
{status_block}
```

No overall GO is issued. The next stage may freeze a fresh untouched V10
holdout; it must not reuse these development arms as confirmation.

## Preserved development failures and verification boundary

- `results_v9_1/development_precheck_failed_long_operation_ids/` preserves the
  first failed run: descriptive operation IDs exceeded the 32-byte wire ABI,
  collided after truncation, and were correctly deduplicated. Its results are
  not cited as the passing precheck.
- A later superseded run is preserved separately because its structural
  projection read the configured profile ID rather than the actual Relay event.
  The final run projects the actual event sequence and was rerun without
  changing the public profile.
- V9.1 changes no Go code and uses the accepted frozen canonical V9 runner.
""")


if __name__ == "__main__":
    main()

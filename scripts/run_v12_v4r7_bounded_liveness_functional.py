from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
import time
import traceback
from collections.abc import Awaitable, Mapping, MutableSequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v12_duplex_functional import build_workload, run_one
from v11_full_scope.frameworks import (
    _make_structured_function,
    native_implementation,
    run_framework_case,
)
from v11_online.frameworks import (
    MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
    _ordered_outcomes,
    _private_routed_names,
    prewarm_framework,
    run_online_framework_workflow,
    trajectory_projection,
)
from v11_online.session import CanonicalOnlineSession
from v12_timing.profile import duplex_provider_bound_p10_profile
from v12_timing.projection import (
    DUPLEX_TIMING_ONLY_VIEW,
    load_registry_server_trace,
    registry_timing_projection,
    relay_timing_projection,
)

FREEZE = ROOT / "V12_V4R7_BOUNDED_LIVENESS_FUNCTIONAL_FREEZE.json"
STRESS = "CAUSAL_DEPTH_50_BOUNDED_HORIZON_STRESS"


def _stress_workload(framework: str, identity: str):
    return build_workload("CAUSAL_DEPTH_50", framework, identity)


def _run_microsoft_parallel_capacity(cases, implementation) -> dict[str, Any]:
    from agent_framework import (
        Agent,
        BaseChatClient,
        ChatResponse,
        Content,
        FunctionInvocationLayer,
        Message,
        tool,
    )

    outcomes = []
    executed_operation_ids: list[str] = []
    outcomes_by_operation = {}
    boundary: list[tuple[str, Any]] = []
    routed_names = _private_routed_names(cases)
    registered = []
    calls = []
    for case, routed_name in zip(cases, routed_names, strict=True):

        def invoke(value_case, values):
            outcome = implementation(value_case, values)
            outcomes.append(outcome)
            executed_operation_ids.append(value_case.operation_id)
            outcomes_by_operation[value_case.operation_id] = outcome
            return outcome

        function = _make_structured_function(case, invoke, boundary)
        registered.append(
            tool(name=routed_name, approval_mode="never_require")(function)
        )
        calls.append((routed_name, case.arguments, case.operation_id))

    class CapacityClient(FunctionInvocationLayer[Any], BaseChatClient[Any]):
        def __init__(self) -> None:
            super().__init__(
                middleware=[],
                function_invocation_configuration={
                    "max_iterations": MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
                    "max_function_calls": 50,
                },
            )
            self.iteration = 0

        def _inner_get_response(
            self,
            *,
            messages: MutableSequence[Any],
            stream: bool,
            options: Mapping[str, Any],
            **_kwargs: Any,
        ) -> Awaitable[Any]:
            if stream:
                raise NotImplementedError("capacity client is non-streaming")

            async def response():
                if self.iteration == 0:
                    value = ChatResponse(
                        messages=Message(
                            "assistant",
                            [
                                Content.from_function_call(
                                    call_id=operation_id,
                                    name=name,
                                    arguments=arguments,
                                )
                                for name, arguments, operation_id in calls
                            ],
                        )
                    )
                else:
                    value = ChatResponse(
                        messages=Message(
                            "assistant", ["framework-completed:PARALLEL_ACTIONS"]
                        )
                    )
                self.iteration += 1
                return value

            return response()

    async def execute() -> dict[str, Any]:
        client = CapacityClient()
        parent = Agent(
            client=client,
            name="V12V4R7MicrosoftCapacity50",
            instructions="Execute all predeclared independent capacity actions.",
            tools=registered,
        )
        result = await parent.run("bounded-liveness-capacity-50")
        ordered = _ordered_outcomes(
            "Microsoft", cases, executed_operation_ids, outcomes_by_operation
        )
        return {
            "framework": "Microsoft Agent Framework",
            "workflow": "PARALLEL_ACTIONS",
            "projection": trajectory_projection(cases, ordered, result.text),
            "native_framework_api": "agent_framework.Agent.run",
            "private_execution_configuration": {
                "max_iterations": MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
                "max_function_calls": 50,
                "call_batch_count": 1,
                "source": "PUBLIC_MAX_REAL_OPERATIONS",
            },
        }

    return asyncio.run(execute())


def _capacity_workflow_runner(framework, workflow, cases, implementation):
    if workflow != "PARALLEL_ACTIONS":
        raise ValueError("capacity runner requires PARALLEL_ACTIONS")
    if framework == "Microsoft Agent Framework":
        return _run_microsoft_parallel_capacity(cases, implementation)
    return run_online_framework_workflow(framework, workflow, cases, implementation)


def _run_bounded_stress(output: Path, framework: str, identity: str) -> dict[str, Any]:
    profile = duplex_provider_bound_p10_profile()
    workflow, cases = _stress_workload(framework, identity)
    prewarm_framework(framework)
    native = [run_framework_case(case, native_implementation) for case in cases]
    framework_exception = ""
    with CanonicalOnlineSession(output, cases, public_profile=profile) as session:
        try:
            run_online_framework_workflow(
                framework, workflow, cases, session.implementation()
            )
        except AssertionError as error:
            # The framework-level exact-count assertion is the historical oracle
            # being superseded. Runtime/session evidence below must still account
            # for every intended operation under the bounded admission contract.
            framework_exception = str(error)
    if session.trace is None:
        raise RuntimeError("bounded-horizon stress produced no runtime trace")
    trace = session.trace
    expected = [case.operation_id for case in cases]
    accepted = list(trace.get("accepted_operation_ids", []))
    rejected = list(trace.get("resolved_not_admitted_ids", []))
    results = list(trace.get("results", []))
    providers = list(trace.get("provider_diagnostics", []))
    lifecycle = session.lifecycle
    intents = [
        str(row["operation_id"])
        for row in lifecycle
        if row["stage"] == "ACTION_INTENT_SUBMITTED"
    ]
    recovered = [
        str(row["operation_id"])
        for row in lifecycle
        if row["stage"] == "DYNAMIC_PIR_DESCRIPTOR_RECOVERED"
    ]
    delivered = [
        str(row["operation_id"])
        for row in lifecycle
        if row["stage"] == "FRAMEWORK_RESULT_DELIVERED"
    ]
    semantic_failures: list[dict[str, object]] = []
    native_by_id = {
        case.operation_id: record for case, record in zip(cases, native, strict=True)
    }
    for row in results:
        operation_id = str(row["operation_id"])
        expected_record = native_by_id[operation_id]
        observed_result = base64.b64decode(row.get("payload") or "").decode(
            "utf-8", errors="replace"
        )
        if (
            int(row["status"]) != 2
            or expected_record.operation_outcome_semantics != "READ_ONLY:SUCCESS"
            or observed_result != expected_record.result
        ):
            semantic_failures.append(
                {
                    "operation_id": operation_id,
                    "status": row["status"],
                    "observed_result": observed_result,
                    "expected_result": expected_record.result,
                }
            )
    relay = list(trace.get("public_relay_events", []))
    releases = list(trace.get("gateway_response_releases", []))
    registry_root = output / "pir"
    registry_rows = load_registry_server_trace(
        registry_root / "server_visible_trace.jsonl"
    )
    registry_summary = json.loads(
        (registry_root / "online_query_summary.json").read_text(encoding="utf-8")
    )
    relay_projection = relay_timing_projection(
        {"public_relay_events": relay},
        expected_rounds=profile.total_rounds,
        expected_request_bytes=1079,
        expected_response_bytes=800,
        require_complete_application_timing=True,
        require_duplex_application_timing=True,
    )
    registry_projection = registry_timing_projection(
        registry_rows,
        profile_id=profile.profile_id,
        pir_period_ms=profile.pir_resolution_period_ms,
        opportunities=profile.pir_resolution_opportunities,
        require_complete_application_timing=True,
    )
    common_checks = {
        "profile_exact": trace.get("profile_id") == profile.profile_id,
        "relay_R": len(relay) == 521,
        "registry_Q": len(registry_rows) == 100,
        "relay_projection_complete": relay_projection["view"]
        == DUPLEX_TIMING_ONLY_VIEW,
        "registry_projection_complete": registry_projection["view"]
        == "TIMING_ONLY_VIEW",
        "fixed_request_bytes": all(int(row["request_length"]) == 1079 for row in relay),
        "fixed_response_bytes": all(
            int(row["response_length"]) == 800 for row in relay
        ),
        "gateway_release_inventory": len(releases) == 521
        and all(
            bool(row.get("release_attempted"))
            and bool(row.get("response_write_completed"))
            for row in releases
        ),
        "public_transcript_complete": trace.get("public_transcript_complete") is True,
        "session_complete": trace.get("session_status") == "COMPLETE",
        "no_infrastructure_liveness_failure": trace.get(
            "infrastructure_liveness_failure"
        )
        is False,
    }
    bounded_checks = {
        "all_50_intents_observed": intents == expected,
        "all_50_descriptors_resolved": recovered == expected,
        "accepted_prefix": accepted == expected[: len(accepted)],
        "post_window_rejected_suffix": rejected == expected[len(accepted) :],
        "inventory_reconciles": len(accepted) + len(rejected) == 50,
        "accepted_results_exact": [row["operation_id"] for row in results] == accepted,
        "accepted_provider_success": [row["operation_id"] for row in providers]
        == accepted
        and all(row["class"] == "PROVIDER_OK" for row in providers),
        "accepted_delivery_order": delivered == accepted,
        "semantic_failures_zero": not semantic_failures,
        "pending_zero": not trace.get("pending_operation_ids", []),
        "silent_loss_zero": int(trace.get("silent_committed_result_losses", -1)) == 0,
        "profile_overflow_zero": int(trace.get("profile_overflow_events", -1)) == 0,
        "fixed_registry_schedule": int(registry_summary["query_count"]) == 100,
    }
    result = {
        "schema": "AgentTool.V12V4R7BoundedHorizonStress/1",
        "identity": identity,
        "framework": framework,
        "workload": STRESS,
        "intended_causal_depth": 50,
        "admitted_within_public_window": len(accepted),
        "post_window_not_admitted": len(rejected),
        "first_operation_outside_window_index_one_based": (
            len(accepted) + 1 if rejected else None
        ),
        "first_operation_outside_window_id": rejected[0] if rejected else None,
        "semantic_failures": semantic_failures,
        "silent_losses": int(trace.get("silent_committed_result_losses", -1)),
        "framework_exact_count_exception": framework_exception,
        "common_checks": common_checks,
        "bounded_contract_checks": bounded_checks,
        "common_integrity_pass": all(common_checks.values()),
        "functional_pass": all(common_checks.values()) and all(bounded_checks.values()),
        "guaranteed_causal_depth_50": "NOT_CLAIMED",
        "classifier_training_runs": 0,
        "auc_calculations": 0,
        "retries": 0,
    }
    (output / "bounded_horizon_stress_verdict.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, default=FREEZE)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(
            f"refusing to overwrite functional evidence: {args.output}"
        )
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    if freeze.get("frozen_before_execution") is not True:
        raise ValueError("bounded-liveness functional identities are not frozen")
    profile = duplex_provider_bound_p10_profile()
    if (
        freeze["profile"]["profile_id"] != profile.profile_id
        or int(freeze["profile"]["R"]) != profile.total_rounds
    ):
        raise ValueError("frozen profile disagrees with V4R7 runtime")
    identities = list(freeze["identities"])
    if len(identities) != 16 or len({row["identity"] for row in identities}) != 16:
        raise ValueError("frozen functional identity inventory is malformed")
    args.output.mkdir(parents=True)
    ledger = args.output / "execution_ledger.jsonl"
    results: list[dict[str, Any]] = []
    previous_hash = "0" * 64
    common_abort = False
    for item in identities:
        unit_root = args.output / f"{int(item['ordinal']):02d}_{item['identity']}"
        started_ns = time.time_ns()
        try:
            if item["workload"] == STRESS:
                result = _run_bounded_stress(
                    unit_root, str(item["framework"]), str(item["identity"])
                )
            else:
                result = run_one(
                    unit_root,
                    profile,
                    str(item["framework"]),
                    str(item["workload"]),
                    str(item["identity"]),
                    allow_successful_late_releases=True,
                    require_strict_causal=item["workload"] != "CAPACITY_50",
                    workflow_runner=(
                        _capacity_workflow_runner
                        if item["workload"] == "CAPACITY_50"
                        else None
                    ),
                )
            result["pass"] = bool(
                result.get("common_integrity_pass") and result.get("functional_pass")
            )
        except Exception as error:  # noqa: BLE001 - preserve immutable unit failure
            result = {
                "identity": item["identity"],
                "framework": item["framework"],
                "workload": item["workload"],
                "common_integrity_pass": False,
                "functional_pass": False,
                "pass": False,
                "exception_class": type(error).__name__,
                "exception_string": str(error),
                "traceback": traceback.format_exc(),
                "classifier_training_runs": 0,
                "auc_calculations": 0,
                "retries": 0,
            }
        result["started_ns"] = started_ns
        result["ended_ns"] = time.time_ns()
        results.append(result)
        payload = {
            "ordinal": item["ordinal"],
            "identity": item["identity"],
            "framework": item["framework"],
            "workload": item["workload"],
            "pass": result["pass"],
            "common_integrity_pass": result["common_integrity_pass"],
            "previous_sha256": previous_hash,
            "retries": 0,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        import hashlib

        previous_hash = hashlib.sha256(encoded).hexdigest()
        payload["record_sha256"] = previous_hash
        with ledger.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        if not bool(result["common_integrity_pass"]):
            common_abort = True
            break

    def unit(framework: str, workload: str) -> dict[str, Any] | None:
        return next(
            (
                row
                for row in results
                if row["framework"] == framework and row["workload"] == workload
            ),
            None,
        )

    smoke_workloads = {
        "ORDINARY_TOOL",
        "AGENT_AS_TOOL_TRANSITION",
        "PROVIDER_EARLY_10",
        "PROVIDER_LATE_10",
        "DESCRIPTOR_TRANSITIONS_K6",
    }
    smoke_rows = [row for row in results if row["workload"] in smoke_workloads]
    capacity_rows = [row for row in results if row["workload"] == "CAPACITY_50"]
    stress_rows = [row for row in results if row["workload"] == STRESS]
    full_correct = (
        len(results) == 16
        and not common_abort
        and all(bool(row["pass"]) for row in results)
    )
    operation_capacity = len(capacity_rows) == 2 and all(
        bool(row["pass"]) for row in capacity_rows
    )
    smoke_scope = len(smoke_rows) == 10 and all(bool(row["pass"]) for row in smoke_rows)
    microsoft_cache = unit("Microsoft Agent Framework", "CACHE_REUSE_30")
    readiness = (
        full_correct
        and operation_capacity
        and smoke_scope
        and microsoft_cache is not None
        and bool(microsoft_cache["pass"])
    )
    summary = {
        "schema": "AgentTool.V12V4R7BoundedLivenessFunctionalClosure/1",
        "profile_id": profile.profile_id,
        "planned_units": 16,
        "executed_units": len(results),
        "passed_units": sum(bool(row["pass"]) for row in results),
        "failed_units": sum(not bool(row["pass"]) for row in results),
        "retries": 0,
        "common_integrity_abort": common_abort,
        "smoke_scope_functional_mechanisms": "PASS" if smoke_scope else "FAIL",
        "full_fixed_h_functional_correctness": "PASS" if full_correct else "FAIL",
        "operation_capacity_m50": "PASS" if operation_capacity else "FAIL",
        "microsoft_cache_reuse_30": (
            "PASS"
            if microsoft_cache is not None and microsoft_cache["pass"]
            else "FAIL"
        ),
        "causal_depth_50_stress": stress_rows,
        "guaranteed_causal_depth_50": "NOT_CLAIMED",
        "ready_for_development_duplex_repair_smoke": readiness,
        "protected_classifier_runs": 0,
        "protected_auc_calculations": 0,
        "results": results,
    }
    (args.output / "BOUNDED_LIVENESS_FUNCTIONAL_SUMMARY.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if full_correct else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterable, Awaitable, Mapping, MutableSequence, Sequence
from dataclasses import dataclass, replace
from typing import Any

from v11_full_scope.frameworks import _make_structured_function
from v11_full_scope.models import AgentServiceSubtype, V11ActionCase, V11ActionOutcome
from v11_online.frameworks import (
    MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
    SYSTEM_MAX_REAL_OPERATIONS_PUBLIC,
    run_online_framework_workflow,
)
from v12_timing.isolated_tasks import build_primary_workload

PHASE = "V12-MICROSOFT-T7-SEMANTIC-RELIABILITY-ROOT-CAUSE-CLOSURE"
BASE_ABORT_EVIDENCE = "f063d8bec6696f003020b1b6dab71e918e073aac"
PROTOCOL_BASE_SHA = "3dde92221b274148f4926de4d4df07d8a6c64cd5"
FAILED_IMMUTABLE_IDENTITY = "DEV-TAD-P10-T7-MS-SENTINEL-B0075-C1"
FRAMEWORK = "Microsoft Agent Framework"
REPETITIONS_PER_COORDINATE = 200
COORDINATES = (
    "D1_T7_CLASS0_ADAPTER",
    "D2_T7_CLASS1_ADAPTER",
    "D3_ORDINARY_TOOL_ONLY",
    "D4_AGENT_AS_TOOL_ONLY",
    "D5_MIXED_UNIQUE_ROUTED_NAMES",
    "D6_MIXED_REPEATED_ROUTED_NAMES",
)


@dataclass(frozen=True)
class DiagnosticSpec:
    coordinate: str
    repetition: int
    identity: str
    operation_ids: tuple[str, ...]
    construction: str
    routed_name_policy: str


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _coordinate_number(coordinate: str) -> int:
    return COORDINATES.index(coordinate) + 1


def diagnostic_spec(coordinate: str, repetition: int) -> DiagnosticSpec:
    if coordinate not in COORDINATES:
        raise ValueError("unknown Microsoft T7 RCA coordinate")
    if not 0 <= repetition < REPETITIONS_PER_COORDINATE:
        raise ValueError("RCA repetition outside frozen denominator")
    number = _coordinate_number(coordinate)
    identity = f"DEV-T7-MS-RCA-D{number}-R{repetition:04d}"
    operation_count = 1 if number in (3, 4) else 2
    operation_ids = tuple(
        f"opRCAD{number}R{repetition:04d}O{index:02d}" for index in range(operation_count)
    )
    construction = {
        1: "ACTUAL_AGENTTOOL_T7_CLASS0_ADAPTER",
        2: "ACTUAL_AGENTTOOL_T7_CLASS1_ADAPTER",
        3: "MINIMAL_ORDINARY_TOOL_ONLY",
        4: "MINIMAL_AGENT_AS_TOOL_ONLY",
        5: "MINIMAL_MIXED_TOOL_AGENT_AS_TOOL",
        6: "MINIMAL_MIXED_TOOL_AGENT_AS_TOOL",
    }[number]
    routed_name_policy = "UNIQUE_PER_IDENTITY" if number == 5 else "CURRENT_REPEATED_NAMES"
    return DiagnosticSpec(
        coordinate,
        repetition,
        identity,
        operation_ids,
        construction,
        routed_name_policy,
    )


def diagnostic_schedule() -> tuple[DiagnosticSpec, ...]:
    return tuple(
        diagnostic_spec(coordinate, repetition)
        for repetition in range(REPETITIONS_PER_COORDINATE)
        for coordinate in COORDINATES
    )


def _t7_cases(spec: DiagnosticSpec, *, label: int) -> tuple[V11ActionCase, ...]:
    source = build_primary_workload(
        "T7", FRAMEWORK, label, block=spec.repetition, stage="CONTROL", delta_ms=10
    )
    cases = tuple(
        replace(
            case,
            case_id=f"{spec.identity}-CASE-{index}",
            operation_id=spec.operation_ids[index],
        ).validate()
        for index, case in enumerate(source.cases)
    )
    return cases


def _semantic_outcome(case: V11ActionCase) -> V11ActionOutcome:
    return V11ActionOutcome(
        result=f"semantic-result:{case.operation_id}",
        effect_count=0,
        outcome_semantics=f"{case.effect_semantics}:SUCCESS",
        provider_visible_logical_request={
            "logical_action": case.logical_action_name,
            "arguments": dict(case.arguments),
        },
        evidence={"semantic_rca_only": True},
    )


def _classification(expected: Sequence[str], executed: Sequence[str], exception: str | None) -> str:
    if exception is not None:
        return "FRAMEWORK_EXCEPTION"
    if list(executed) == list(expected):
        return "ALL_EXPECTED_OPERATIONS_EXECUTED"
    if not executed:
        return "ZERO_EXECUTED"
    if len(expected) == 2 and list(executed) == [expected[0]]:
        return "FIRST_EXECUTED_ONLY"
    if len(expected) == 2 and list(executed) == [expected[1]]:
        return "SECOND_EXECUTED_ONLY"
    return "OTHER_SEMANTIC_MISMATCH"


def _actual_adapter_diagnostic(spec: DiagnosticSpec, *, label: int) -> dict[str, Any]:
    cases = _t7_cases(spec, label=label)
    executed: list[str] = []
    events: list[dict[str, Any]] = [
        {"stage": "PARENT_AGENT_RUN_ENTRY", "source": "AgentTool_adapter_call"}
    ]
    exception: str | None = None

    def implementation(case: V11ActionCase, _values: dict[str, Any]) -> V11ActionOutcome:
        subtype = case.agent_service_subtype.value if case.agent_service_subtype else None
        events.append(
            {
                "stage": "AGENTTOOL_IMPLEMENTATION_ENTERED",
                "operation_id": case.operation_id,
                "agent_service_subtype": subtype,
            }
        )
        executed.append(case.operation_id)
        return _semantic_outcome(case)

    result: dict[str, Any] | None = None
    try:
        result = run_online_framework_workflow(FRAMEWORK, "TOOL_TO_AGENT_AS_TOOL" if label else "DYNAMIC_SEQUENCE", list(cases), implementation)
        events.append({"stage": "PARENT_AGENT_RUN_RETURNED"})
    except Exception as error:  # noqa: BLE001 - semantic outcome category, never retried
        exception = f"{type(error).__name__}: {error}"
        events.append({"stage": "FRAMEWORK_EXCEPTION", "exception": exception})
    projected_ids = (
        [str(row["operation_id"]) for row in result["projection"]["trajectory"]]
        if result is not None
        else []
    )
    return {
        "expected_operation_ids": list(spec.operation_ids),
        "executed_operation_ids": executed,
        "projected_operation_ids": projected_ids,
        "events": events,
        "exception": exception,
        "registered_tool_names": ["acv_private_route_000", "acv_private_route_001"],
        "registered_tool_count": 2,
    }


def _direct_diagnostic(spec: DiagnosticSpec) -> dict[str, Any]:
    from agent_framework import (
        Agent,
        BaseChatClient,
        ChatResponse,
        ChatResponseUpdate,
        Content,
        FunctionInvocationLayer,
        Message,
        ResponseStream,
        tool,
    )

    label_one_cases = _t7_cases(
        replace(
            spec,
            operation_ids=(
                spec.operation_ids
                if len(spec.operation_ids) == 2
                else (f"opRCAD{_coordinate_number(spec.coordinate)}R{spec.repetition:04d}O00", f"opRCAD{_coordinate_number(spec.coordinate)}R{spec.repetition:04d}O01")
            ),
        ),
        label=1,
    )
    if spec.coordinate == "D3_ORDINARY_TOOL_ONLY":
        cases = (replace(label_one_cases[0], operation_id=spec.operation_ids[0]).validate(),)
    elif spec.coordinate == "D4_AGENT_AS_TOOL_ONLY":
        cases = (replace(label_one_cases[1], operation_id=spec.operation_ids[0]).validate(),)
    else:
        cases = label_one_cases

    events: list[dict[str, Any]] = []
    executed: list[str] = []

    def implementation(case: V11ActionCase, _values: dict[str, Any]) -> V11ActionOutcome:
        events.append(
            {
                "stage": "AGENTTOOL_IMPLEMENTATION_ENTERED",
                "operation_id": case.operation_id,
                "agent_service_subtype": (
                    case.agent_service_subtype.value if case.agent_service_subtype else None
                ),
            }
        )
        executed.append(case.operation_id)
        return _semantic_outcome(case)

    suffix = hashlib.sha256(spec.identity.encode()).hexdigest()[:10]
    names = [f"acv_private_route_{index:03d}" for index in range(len(cases))]
    if spec.routed_name_policy == "UNIQUE_PER_IDENTITY":
        names = [f"{name}_{suffix}" for name in names]

    registered: list[Any] = []
    calls: list[tuple[str, dict[str, Any], str]] = []
    schemas: dict[str, Any] = {}

    def child_client_for(bound_case: V11ActionCase) -> Any:
        class ChildClient(BaseChatClient[Any]):
            def __init__(self) -> None:
                super().__init__()
                self.used = False

            def make_outcome(self) -> V11ActionOutcome:
                if self.used:
                    raise AssertionError("diagnostic child Agent executed more than once")
                self.used = True
                events.append(
                    {
                        "stage": "CHILD_CLIENT_INVOKED",
                        "operation_id": bound_case.operation_id,
                    }
                )
                return implementation(
                    bound_case,
                    bound_case.argument_schema.validate_values(bound_case.arguments),
                )

            def _inner_get_response(
                self, *, messages: MutableSequence[Any], stream: bool, options: Mapping[str, Any], **_kwargs: Any
            ) -> Awaitable[Any] | ResponseStream[Any, Any]:
                if not stream:
                    async def response() -> ChatResponse[Any]:
                        value = self.make_outcome()
                        return ChatResponse(messages=Message("assistant", [value.result]))

                    return response()

                async def updates() -> AsyncIterable[Any]:
                    value = self.make_outcome()
                    yield ChatResponseUpdate(
                        contents=[Content.from_text(value.result)],
                        role="assistant",
                        finish_reason="stop",
                    )

                def finalize(values: Sequence[Any]) -> ChatResponse[Any]:
                    return ChatResponse.from_updates(
                        values, output_format_type=options.get("response_format")
                    )

                return ResponseStream(updates(), finalizer=finalize)

        return ChildClient()

    for case, routed_name in zip(cases, names, strict=True):
        if case.agent_service_subtype is AgentServiceSubtype.AGENT_AS_TOOL:
            agent_case = case
            child = Agent(
                client=child_client_for(agent_case),
                name=f"RCAChild_{spec.repetition}",
                instructions="Return semantic diagnostic result",
            )
            child_tool = child.as_tool(
                name=routed_name, arg_name="task", approval_mode="never_require"
            )
            registered.append(child_tool)
            calls.append(
                (
                    child_tool.name,
                    {"task": str(next(iter(agent_case.arguments.values())))},
                    agent_case.operation_id,
                )
            )
            schemas[child_tool.name] = child_tool.parameters()
        else:
            ordinary_case = case

            def invoke(
                _value_case: V11ActionCase,
                values: dict[str, Any],
                *,
                bound_case: V11ActionCase = ordinary_case,
            ) -> V11ActionOutcome:
                events.append(
                    {"stage": "ORDINARY_TOOL_INVOKED", "operation_id": bound_case.operation_id}
                )
                return implementation(bound_case, values)

            boundary: list[tuple[str, Any]] = []
            function = _make_structured_function(ordinary_case, invoke, boundary)
            ordinary_tool = tool(name=routed_name, approval_mode="never_require")(function)
            registered.append(ordinary_tool)
            calls.append((ordinary_tool.name, ordinary_case.arguments, ordinary_case.operation_id))
            schemas[ordinary_tool.name] = ordinary_tool.parameters()

    class ParentClient(FunctionInvocationLayer[Any], BaseChatClient[Any]):
        def __init__(self) -> None:
            super().__init__(
                middleware=[],
                function_invocation_configuration={
                    "max_iterations": MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
                    "max_function_calls": SYSTEM_MAX_REAL_OPERATIONS_PUBLIC,
                },
            )
            self.iteration = 0
            self.observed_result_call_ids: list[str] = []

        def _inner_get_response(
            self,
            *,
            messages: MutableSequence[Any],
            stream: bool,
            options: Mapping[str, Any],
            **_kwargs: Any,
        ) -> Awaitable[Any]:
            if stream:
                raise NotImplementedError("RCA parent is non-streaming")

            async def response() -> ChatResponse[Any]:
                events.append(
                    {"stage": "PARENT_CLIENT_ENTERED", "iteration": self.iteration}
                )
                for message in messages:
                    for content in getattr(message, "contents", []):
                        if getattr(content, "type", "") == "function_result":
                            call_id = str(getattr(content, "call_id", ""))
                            if call_id not in self.observed_result_call_ids:
                                self.observed_result_call_ids.append(call_id)
                                events.append(
                                    {"stage": "FUNCTION_RESULT_RETURNED", "call_id": call_id}
                                )
                if self.iteration < len(calls):
                    name, arguments, operation_id = calls[self.iteration]
                    events.append(
                        {
                            "stage": "FUNCTION_CALL_CONTENT_CREATED",
                            "iteration": self.iteration,
                            "name": name,
                            "call_id": operation_id,
                        }
                    )
                    value = ChatResponse(
                        messages=Message(
                            "assistant",
                            [
                                Content.from_function_call(
                                    call_id=operation_id,
                                    name=name,
                                    arguments=arguments,
                                )
                            ],
                        )
                    )
                else:
                    value = ChatResponse(
                        messages=Message("assistant", [f"rca-complete:{spec.identity}"])
                    )
                self.iteration += 1
                return value

            return response()

    parent_client = ParentClient()
    parent = Agent(
        client=parent_client,
        name=f"RCAParent_{spec.repetition}",
        instructions="Execute semantic diagnostics causally",
        tools=registered,
    )
    exception: str | None = None
    result_text: str | None = None

    async def execute() -> None:
        nonlocal result_text
        events.append({"stage": "PARENT_AGENT_RUN_ENTRY"})
        result = await parent.run("development-only-semantic-rca")
        result_text = result.text
        events.append({"stage": "PARENT_AGENT_RUN_RETURNED"})

    try:
        asyncio.run(execute())
    except Exception as error:  # noqa: BLE001 - semantic outcome category, never retried
        exception = f"{type(error).__name__}: {error}"
        events.append({"stage": "FRAMEWORK_EXCEPTION", "exception": exception})

    return {
        "expected_operation_ids": list(spec.operation_ids),
        "executed_operation_ids": executed,
        "events": events,
        "exception": exception,
        "result_text": result_text,
        "registered_tool_names": [tool_item.name for tool_item in registered],
        "registered_tool_count": len(registered),
        "registered_tool_schemas": schemas,
        "generated_call_ids": [call_id for _, _, call_id in calls],
        "observed_result_call_ids": parent_client.observed_result_call_ids,
        "function_invocation_configuration": dict(
            parent_client.function_invocation_configuration
        ),
    }


def run_diagnostic(spec: DiagnosticSpec) -> dict[str, Any]:
    if spec.coordinate == "D1_T7_CLASS0_ADAPTER":
        detail = _actual_adapter_diagnostic(spec, label=0)
    elif spec.coordinate == "D2_T7_CLASS1_ADAPTER":
        detail = _actual_adapter_diagnostic(spec, label=1)
    else:
        detail = _direct_diagnostic(spec)
    classification = _classification(
        spec.operation_ids,
        detail["executed_operation_ids"],
        detail["exception"],
    )
    return {
        "schema": "AgentTool.V12MicrosoftT7SemanticRCAResult/1",
        "identity": spec.identity,
        "coordinate": spec.coordinate,
        "repetition": spec.repetition,
        "construction": spec.construction,
        "routed_name_policy": spec.routed_name_policy,
        "classification": classification,
        "semantic_only": True,
        "timing_features_collected": False,
        "classifier_training": False,
        "auc_calculation": False,
        **detail,
    }


def build_freeze_manifest(
    *,
    execution_source_commit: str,
    framework_commit: str,
    framework_source_hashes: Mapping[str, str],
    analysis_hashes: Mapping[str, str],
) -> dict[str, Any]:
    identities = [
        {
            "execution_ordinal": ordinal,
            "coordinate": spec.coordinate,
            "repetition": spec.repetition,
            "identity": spec.identity,
            "operation_ids": list(spec.operation_ids),
            "construction": spec.construction,
            "routed_name_policy": spec.routed_name_policy,
        }
        for ordinal, spec in enumerate(diagnostic_schedule())
    ]
    manifest: dict[str, Any] = {
        "schema": "AgentTool.V12MicrosoftT7SemanticRCAFreeze/1",
        "phase": PHASE,
        "base_abort_evidence": BASE_ABORT_EVIDENCE,
        "protocol_base_sha": PROTOCOL_BASE_SHA,
        "failed_immutable_identity": FAILED_IMMUTABLE_IDENTITY,
        "failed_identity_reexecuted": False,
        "initial_root_cause_status": "INTERMITTENT_MICROSOFT_T7_PARENT_INVOCATION_FAILURE_ROOT_CAUSE_OPEN",
        "coordinates": list(COORDINATES),
        "repetitions_per_coordinate": REPETITIONS_PER_COORDINATE,
        "diagnostic_identity_count": len(identities),
        "execution_order": "INTERLEAVED_BY_REPETITION_THEN_D1_THROUGH_D6",
        "retry_policy": "ZERO_RETRIES_EACH_IDENTITY_EXECUTES_ONCE",
        "identity_search": False,
        "semantic_only": True,
        "timing_trace_access": False,
        "timing_classifier_training": False,
        "auc_calculation": False,
        "execution_source_commit": execution_source_commit,
        "framework_commit": framework_commit,
        "framework_source_hashes": dict(sorted(framework_source_hashes.items())),
        "analysis_hashes": dict(sorted(analysis_hashes.items())),
        "function_invocation_configuration": {
            "max_iterations": MICROSOFT_NATIVE_MAX_ITERATIONS_PUBLIC,
            "max_function_calls": SYSTEM_MAX_REAL_OPERATIONS_PUBLIC,
        },
        "permanent_exclusions": [
            "P10_SENTINEL",
            "P10_FULL",
            "P20_P25_PROTECTED_DEVELOPMENT",
            "TIMING_CONFIRMATION",
            "FINAL_V12_HOLDOUT",
        ],
        "identity_manifest": identities,
    }
    manifest["payload_sha256"] = _canonical_sha256(manifest)
    return manifest


def validate_freeze_manifest(manifest: Mapping[str, Any]) -> None:
    payload = dict(manifest)
    expected_hash = str(payload.pop("payload_sha256"))
    if _canonical_sha256(payload) != expected_hash:
        raise ValueError("RCA freeze payload hash mismatch")
    if manifest["failed_immutable_identity"] != FAILED_IMMUTABLE_IDENTITY:
        raise ValueError("failed immutable identity drifted")
    if manifest["failed_identity_reexecuted"] is not False:
        raise ValueError("failed sentinel identity must never be reexecuted")
    identities = list(manifest["identity_manifest"])
    expected = diagnostic_schedule()
    if len(identities) != 1200 or len(expected) != 1200:
        raise ValueError("RCA denominator drifted")
    if len({row["identity"] for row in identities}) != 1200:
        raise ValueError("RCA identities are not unique")
    if FAILED_IMMUTABLE_IDENTITY in {row["identity"] for row in identities}:
        raise ValueError("failed sentinel identity entered the RCA matrix")
    for ordinal, (row, spec) in enumerate(zip(identities, expected, strict=True)):
        if row["execution_ordinal"] != ordinal or row["identity"] != spec.identity:
            raise ValueError("RCA execution order drifted")
        if row["operation_ids"] != list(spec.operation_ids):
            raise ValueError("RCA operation IDs drifted")

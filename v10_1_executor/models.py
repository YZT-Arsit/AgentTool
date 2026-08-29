from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable


SEMANTIC_FIELDS = (
    "selected_logical_action",
    "arguments",
    "provider_visible_logical_request",
    "effect_count",
    "operation_outcome_semantics",
    "result",
    "final_framework_visible_result_state",
)


@dataclass(frozen=True)
class CaseSpec:
    """Generic executable case; source metadata never drives execution."""

    case_id: str
    framework: str
    adapter_id: str
    action_family: str
    prompt: str
    protected_argument: str
    operation_id: str
    capability: str = "tool.read"
    effect_semantics: str = "READ_ONLY"
    scenario: str = "SUCCESS"
    logical_action_name: str = "execute_action"
    argument_name: str = "argument"
    source_path: str = "SYNTHETIC_NON_HOLDOUT_FIXTURE"
    source_line: int = 0

    def validate(self) -> "CaseSpec":
        if self.framework not in {"OpenAI Agents SDK", "Microsoft Agent Framework"}:
            raise ValueError("unsupported framework")
        if self.action_family != "tool":
            raise NotImplementedError("V10.1 generic executable adapter currently supports Tool sites only")
        if self.scenario not in {"SUCCESS", "ERROR", "BOUNDED_TIMEOUT"}:
            raise ValueError("unknown deterministic scenario")
        if not self.operation_id or len(self.operation_id.encode("utf-8")) > 32:
            raise ValueError("operation ID does not fit canonical ABI")
        if not self.logical_action_name.isidentifier() or not self.argument_name.isidentifier():
            raise ValueError("generic Tool adapter requires identifier-safe action and argument names")
        return self


@dataclass(frozen=True)
class ActionOutcome:
    result: str
    effect_count: int
    outcome_semantics: str
    provider_request: dict[str, Any]
    runtime_evidence: dict[str, Any]


@dataclass(frozen=True)
class FrameworkRunEvidence:
    framework: str
    framework_instantiated: bool
    action_registered: bool
    native_action_boundary_reached: bool
    provider_request_observed: bool
    framework_received_result: bool
    selected_logical_action: str
    arguments: str
    action_outcome: ActionOutcome
    final_output: str
    framework_events: tuple[str, ...]
    runtime_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticExecutionRecord:
    selected_logical_action: str
    arguments: str
    provider_visible_logical_request: dict[str, Any]
    effect_count: int
    operation_outcome_semantics: str
    result: str
    final_framework_visible_result_state: dict[str, Any]
    execution_evidence: dict[str, Any]

    def projection(self) -> dict[str, Any]:
        value = asdict(self)
        return {field: value[field] for field in SEMANTIC_FIELDS}


ActionImplementation = Callable[[CaseSpec, str], ActionOutcome]


def semantic_record(evidence: FrameworkRunEvidence, extra: dict[str, Any] | None = None) -> SemanticExecutionRecord:
    proof = {
        "framework": evidence.framework,
        "framework_instantiated": evidence.framework_instantiated,
        "action_registered": evidence.action_registered,
        "native_action_boundary_reached": evidence.native_action_boundary_reached,
        "provider_request_observed": evidence.provider_request_observed,
        "framework_received_result": evidence.framework_received_result,
        "framework_events": list(evidence.framework_events),
        "runtime_evidence": evidence.runtime_evidence,
    }
    if extra:
        proof.update(extra)
    return SemanticExecutionRecord(
        selected_logical_action=evidence.selected_logical_action,
        arguments=evidence.arguments,
        provider_visible_logical_request=evidence.action_outcome.provider_request,
        effect_count=evidence.action_outcome.effect_count,
        operation_outcome_semantics=evidence.action_outcome.outcome_semantics,
        result=evidence.action_outcome.result,
        final_framework_visible_result_state={
            "final_output": evidence.final_output,
            "action_result_received": evidence.framework_received_result,
            "action_result": evidence.action_outcome.result,
        },
        execution_evidence=proof,
    )

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AdapterRegistration:
    adapter_id: str
    framework: str
    supported_action_family: str
    source_compatibility_rule: str
    native_executor: str
    canonical_executor: str
    deterministic_provider_contract: str
    semantic_projection_extractor: str
    holdout_eligible: bool
    limitation: str


REGISTRY = (
    AdapterRegistration(
        "OPENAI_GENERIC_FUNCTION_TOOL_V10_1",
        "OpenAI Agents SDK",
        "tool",
        "frozen corpus row resolves to a locally parseable @tool/@function_tool callable with one str argument; generic action name and argument-name adaptation only",
        "v10_1_executor.semantic.run_native_case",
        "v10_1_executor.semantic.run_canonical_case",
        "LOCAL_DETERMINISTIC_PROVIDER_V10_1",
        "SemanticExecutionRecord.projection",
        True,
        "Does not establish multi-argument/source-body semantics, hosted Tools, streaming, approval, or arbitrary callbacks.",
    ),
    AdapterRegistration(
        "MICROSOFT_GENERIC_FUNCTION_TOOL_V10_1",
        "Microsoft Agent Framework",
        "tool",
        "frozen corpus row resolves to a locally parseable @tool callable with one str argument; generic action name and argument-name adaptation only",
        "v10_1_executor.semantic.run_native_case",
        "v10_1_executor.semantic.run_canonical_case",
        "LOCAL_DETERMINISTIC_PROVIDER_V10_1",
        "SemanticExecutionRecord.projection",
        True,
        "Does not establish multi-argument/source-body semantics, MCP, streaming, approval, workflow, or arbitrary callbacks.",
    ),
    AdapterRegistration(
        "OPENAI_HANDOFF_UNSUPPORTED_V10_1",
        "OpenAI Agents SDK",
        "handoff",
        "native handoff exists, but no frozen canonical semantic bridge maps it without case-specific logic",
        "NOT_REGISTERED",
        "NOT_REGISTERED",
        "NONE",
        "NONE",
        False,
        "Explicitly ineligible rather than inferred from a projection dictionary.",
    ),
    AdapterRegistration(
        "AGENT_AS_TOOL_UNSUPPORTED_V10_1",
        "BOTH",
        "agents_as_tools",
        "native mechanism exists, but no frozen cross-framework canonical adapter in V10.1",
        "NOT_REGISTERED",
        "NOT_REGISTERED",
        "NONE",
        "NONE",
        False,
        "Explicitly ineligible for replacement holdout selection.",
    ),
)


def registry_json() -> list[dict[str, object]]:
    return [asdict(value) for value in REGISTRY]


def eligible_adapter(framework: str, action_family: str) -> AdapterRegistration | None:
    return next((item for item in REGISTRY if item.framework == framework and item.supported_action_family == action_family and item.holdout_eligible), None)

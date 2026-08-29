from __future__ import annotations

from dataclasses import replace

from .models import (
    AgentServiceSubtype,
    ArgumentField,
    ArgumentSchema,
    CanonicalActionFamily,
    V11ActionCase,
)


SCHEMAS_AND_VALUES = (
    (ArgumentSchema("ONE_STR", (ArgumentField("city", "str"),)), {"city": "Paris"}),
    (ArgumentSchema("ONE_INT", (ArgumentField("count", "int"),)), {"count": 3}),
    (ArgumentSchema("ONE_BOOL", (ArgumentField("enabled", "bool"),)), {"enabled": True}),
    (ArgumentSchema("OPTIONAL_PRIMITIVE", (ArgumentField("note", "optional_str"),)), {"note": None}),
    (
        ArgumentSchema("TWO_PRIMITIVES", (ArgumentField("city", "str"), ArgumentField("count", "int"))),
        {"city": "Paris", "count": 3},
    ),
    (
        ArgumentSchema(
            "THREE_PRIMITIVES",
            (ArgumentField("city", "str"), ArgumentField("count", "int"), ArgumentField("enabled", "bool")),
        ),
        {"city": "Paris", "count": 3, "enabled": True},
    ),
    (
        ArgumentSchema("BOUNDED_OBJECT", (ArgumentField("payload", "object"),)),
        {"payload": {"label": "local", "count": 3, "enabled": True}},
    ),
)


def tool_case(
    case_id: str,
    framework: str,
    schema_index: int = 0,
    effect_semantics: str = "READ_ONLY",
    scenario: str = "SUCCESS",
) -> V11ActionCase:
    schema, values = SCHEMAS_AND_VALUES[schema_index]
    return V11ActionCase(
        case_id,
        framework,
        CanonicalActionFamily.TOOL,
        f"v11_tool_{schema_index}",
        schema,
        values,
        effect_semantics,
        scenario,
        ("op" + case_id.replace("-", ""))[:32],
        "tool.read",
        10,
        "agent.tools",
    )


def agent_case(
    case_id: str,
    framework: str,
    subtype: AgentServiceSubtype,
    effect_semantics: str = "READ_ONLY",
    scenario: str = "SUCCESS",
    placement: str = "EXTERNAL",
) -> V11ActionCase:
    schema = ArgumentSchema("AGENT_TASK", (ArgumentField("task", "str"),))
    if placement == "TRUSTED_MODULE_LOCAL":
        agent_id, capability = 20, "agent.internal.20"
    else:
        agent_id = {"READ_ONLY": 11, "IDEMPOTENT_EFFECT": 12, "NON_IDEMPOTENT_EFFECT": 13}[effect_semantics]
        capability = f"agent.service.{agent_id}"
    return V11ActionCase(
        case_id,
        framework,
        CanonicalActionFamily.AGENT_SERVICE,
        f"v11_{subtype.value.lower()}",
        schema,
        {"task": "local deterministic task"},
        effect_semantics,
        scenario,
        ("op" + case_id.replace("-", ""))[:32],
        capability,
        agent_id,
        capability,
        subtype,
        placement=placement,
    )


def with_readiness(case: V11ActionCase, mode: str) -> V11ActionCase:
    return replace(case, continuation={"provider_readiness_mode": mode})

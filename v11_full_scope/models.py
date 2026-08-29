from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class CanonicalActionFamily(str, Enum):
    TOOL = "TOOL"
    EXTERNAL_HTTP = "EXTERNAL_HTTP"
    AGENT_SERVICE = "AGENT_SERVICE"


class AgentServiceSubtype(str, Enum):
    DIRECT_AGENT_SERVICE = "DIRECT_AGENT_SERVICE"
    AGENT_AS_TOOL = "AGENT_AS_TOOL"
    HANDOFF = "HANDOFF"


PRIMITIVE_TYPES = {"str", "int", "bool", "optional_str", "object"}


@dataclass(frozen=True)
class ArgumentField:
    name: str
    primitive_type: str

    def validate(self) -> "ArgumentField":
        if not self.name.isidentifier():
            raise ValueError("argument field name is not an identifier")
        if self.primitive_type not in PRIMITIVE_TYPES:
            raise ValueError("unsupported bounded argument primitive")
        return self


@dataclass(frozen=True)
class ArgumentSchema:
    schema_id: str
    fields: tuple[ArgumentField, ...]

    def validate(self) -> "ArgumentSchema":
        if not self.schema_id or not 1 <= len(self.fields) <= 3:
            raise ValueError("V11 generic Tool schema supports one to three fields")
        for value in self.fields:
            value.validate()
        names = [value.name for value in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("duplicate argument field")
        if any(value.primitive_type == "object" for value in self.fields) and len(self.fields) != 1:
            raise ValueError("bounded object is a standalone structured argument")
        optional = [index for index, value in enumerate(self.fields) if value.primitive_type == "optional_str"]
        if optional and optional != list(range(optional[0], len(self.fields))):
            raise ValueError("optional primitive fields must follow required fields")
        return self

    def validate_values(self, values: dict[str, Any]) -> dict[str, Any]:
        self.validate()
        if set(values) != {value.name for value in self.fields}:
            raise ValueError("argument values do not exactly match the frozen schema")
        result: dict[str, Any] = {}
        for field_value in self.fields:
            value = values[field_value.name]
            if field_value.primitive_type == "str" and not isinstance(value, str):
                raise TypeError("expected str argument")
            if field_value.primitive_type == "int" and (not isinstance(value, int) or isinstance(value, bool)):
                raise TypeError("expected int argument")
            if field_value.primitive_type == "bool" and not isinstance(value, bool):
                raise TypeError("expected bool argument")
            if field_value.primitive_type == "optional_str" and value is not None and not isinstance(value, str):
                raise TypeError("expected optional str argument")
            if field_value.primitive_type == "object":
                if not isinstance(value, dict) or set(value) != {"label", "count", "enabled"}:
                    raise TypeError("bounded object must contain label/count/enabled")
                if not isinstance(value["label"], str) or not isinstance(value["count"], int) or isinstance(value["count"], bool) or not isinstance(value["enabled"], bool):
                    raise TypeError("bounded object field types are invalid")
                encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
                if len(encoded.encode("utf-8")) > 512:
                    raise ValueError("bounded object exceeds the V11 development limit")
            result[field_value.name] = value
        return result


@dataclass(frozen=True)
class V11ActionCase:
    case_id: str
    framework: str
    action_family: CanonicalActionFamily
    logical_action_name: str
    argument_schema: ArgumentSchema
    arguments: dict[str, Any]
    effect_semantics: str
    scenario: str
    operation_id: str
    capability: str
    agent_id: int
    agent_capability: str
    agent_service_subtype: AgentServiceSubtype | None = None
    continuation: dict[str, Any] = field(default_factory=dict)
    placement: str = "EXTERNAL"
    development_fixture: bool = True

    def validate(self) -> "V11ActionCase":
        if not self.development_fixture:
            raise ValueError("V11 package accepts development fixtures only")
        if self.framework not in {"OpenAI Agents SDK", "Microsoft Agent Framework", "FRAMEWORK_NEUTRAL"}:
            raise ValueError("unsupported pinned framework")
        if not self.logical_action_name.isidentifier():
            raise ValueError("action name is not identifier-safe")
        self.argument_schema.validate_values(self.arguments)
        if self.effect_semantics not in {"READ_ONLY", "IDEMPOTENT_EFFECT", "NON_IDEMPOTENT_EFFECT"}:
            raise ValueError("unknown effect semantics")
        if self.scenario not in {"SUCCESS", "ERROR", "BOUNDED_TIMEOUT", "AMBIGUOUS_RESTART"}:
            raise ValueError("unknown development outcome class")
        if not self.operation_id or len(self.operation_id.encode("utf-8")) > 32:
            raise ValueError("operation ID does not fit the canonical ABI")
        if self.action_family is CanonicalActionFamily.AGENT_SERVICE:
            if self.agent_service_subtype is None:
                raise ValueError("Agent-service subtype is required")
        elif self.agent_service_subtype is not None:
            raise ValueError("Agent-service subtype is private metadata only for AGENT_SERVICE")
        if self.placement not in {"EXTERNAL", "TRUSTED_MODULE_LOCAL"}:
            raise ValueError("unknown placement")
        return self

    def logical_arguments_json(self) -> str:
        values = self.argument_schema.validate_values(self.arguments)
        return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class V11ActionOutcome:
    result: str
    effect_count: int
    outcome_semantics: str
    provider_visible_logical_request: dict[str, Any]
    evidence: dict[str, Any]


@dataclass(frozen=True)
class V11SemanticRecord:
    framework: str
    action_family: str
    agent_service_subtype: str | None
    selected_logical_action: str
    arguments: dict[str, Any]
    provider_visible_logical_request: dict[str, Any]
    effect_count: int
    operation_outcome_semantics: str
    result: str
    final_framework_visible_result_state: dict[str, Any]
    runtime_evidence: dict[str, Any]

    def projection(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("runtime_evidence")
        value.pop("framework")
        return value

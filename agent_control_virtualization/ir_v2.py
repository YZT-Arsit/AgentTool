from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping


IR_VERSION = "IR-v2"


class DecisionKind(StrEnum):
    FINAL = "FINAL"
    TOOL_CALL = "TOOL_CALL"
    HANDOFF = "HANDOFF"


class RuntimeState(StrEnum):
    MODEL_READY = "MODEL_READY"
    TOOL_READY = "TOOL_READY"
    MODEL_RESUME = "MODEL_RESUME"
    HANDOFF_READY = "HANDOFF_READY"
    RETURNED = "RETURNED"
    TOOL_ERROR = "TOOL_ERROR"
    MODEL_ERROR = "MODEL_ERROR"
    BOUND_EXCEEDED = "BOUND_EXCEEDED"
    AGENT_CALL_READY = "AGENT_CALL_READY"
    AGENT_RETURN = "AGENT_RETURN"


class StateScope(StrEnum):
    SESSION_PRIVATE = "SESSION_PRIVATE"
    AGENT_PRIVATE = "AGENT_PRIVATE"
    CALL_LOCAL = "CALL_LOCAL"


class StateOpcode(StrEnum):
    STATE_GET = "STATE_GET"
    STATE_SET = "STATE_SET"
    STATE_EXISTS = "STATE_EXISTS"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, object]
    call_id: str

    def canonical_arguments(self) -> str:
        return json.dumps(dict(self.arguments), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class ModelDecision:
    kind: DecisionKind
    final_text: str = ""
    tool_call: ToolCall | None = None
    handoff_target: str = ""
    handoff_call_id: str = ""

    def __post_init__(self) -> None:
        if self.kind == DecisionKind.TOOL_CALL and self.tool_call is None:
            raise ValueError("TOOL_CALL decision requires a structured Tool call")
        if self.kind == DecisionKind.FINAL and self.tool_call is not None:
            raise ValueError("FINAL decision cannot contain a Tool call")
        if self.kind == DecisionKind.HANDOFF and not self.handoff_target:
            raise ValueError("HANDOFF decision requires a target")


@dataclass(frozen=True)
class ContextItem:
    role: str
    content: str
    call_id: str = ""
    tool_name: str = ""

    def canonical(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content,
                "call_id": self.call_id, "tool_name": self.tool_name}


@dataclass(frozen=True)
class AgentProgramV2:
    logical_agent_id: int
    name: str
    instruction_handle: int
    tool_handles: Mapping[str, int]
    handoff_targets: Mapping[str, int]
    max_model_rounds: int = 8
    agent_tool_targets: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_model_rounds < 1:
            raise ValueError("model round bound must be positive")
        if len(set(self.tool_handles.values())) != len(self.tool_handles):
            raise ValueError("Tool handles must be unique within one Agent")


@dataclass(frozen=True)
class ProgramBundleV2:
    workload: str
    framework: str
    source: str
    agents: tuple[AgentProgramV2, ...]

    def by_id(self) -> dict[int, AgentProgramV2]:
        return {agent.logical_agent_id: agent for agent in self.agents}


def private_handle(domain: str, value: str) -> int:
    material = f"{IR_VERSION}|{domain}|{value}".encode("utf-8")
    return int.from_bytes(hashlib.blake2s(material, digest_size=4).digest(), "big")

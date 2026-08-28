from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .ir import AgentCapsule, ControlEvent, ControlRow, Opcode, instruction_handle


class Disposition(StrEnum):
    COMPILED = "COMPILED"
    SHARED_PRIMITIVE = "SHARED_PRIMITIVE"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class Behavior:
    name: str
    kind: str
    disposition: Disposition
    reason: str


@dataclass
class FrameworkWorkload:
    name: str
    framework: str
    source: str
    agents: list[Any]
    unconditional_edges: list[tuple[int, int]] = field(default_factory=list)
    conditional_edges: list[tuple[int, int]] = field(default_factory=list)
    fanout_edges: list[tuple[int, tuple[int, ...]]] = field(default_factory=list)
    extra_behaviors: list[Behavior] = field(default_factory=list)
    native_object_types: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompilationResult:
    workload: str
    framework: str
    source: str
    capsules: tuple[AgentCapsule, ...]
    behaviors: tuple[Behavior, ...]
    native_object_types: tuple[str, ...]

    @property
    def total(self) -> int: return len(self.behaviors)
    @property
    def compiled(self) -> int: return sum(b.disposition == Disposition.COMPILED for b in self.behaviors)
    @property
    def shared(self) -> int: return sum(b.disposition == Disposition.SHARED_PRIMITIVE for b in self.behaviors)
    @property
    def unsupported(self) -> int: return sum(b.disposition == Disposition.UNSUPPORTED for b in self.behaviors)
    @property
    def coverage(self) -> float: return (self.compiled + self.shared) / self.total


def _agent_fields(agent: Any, framework: str) -> tuple[str, Any, list[Any], list[Any], list[Any], list[Any]]:
    name = str(getattr(agent, "name", None) or getattr(agent, "id", "agent"))
    if framework == "OpenAI Agents SDK":
        instructions = getattr(agent, "instructions", None)
        return (name, instructions, list(getattr(agent, "tools", []) or []),
                list(getattr(agent, "handoffs", []) or []),
                list(getattr(agent, "input_guardrails", []) or []),
                list(getattr(agent, "output_guardrails", []) or []))
    options = dict(getattr(agent, "default_options", {}) or {})
    return (name, options.get("instructions"), list(options.get("tools", []) or []), [],
            list(getattr(agent, "middleware", []) or []), [])


def _tool_name(tool: Any) -> str:
    return str(getattr(tool, "name", None) or getattr(tool, "tool_name", None) or type(tool).__name__)


def compile_workload(workload: FrameworkWorkload, base_agent_id: int) -> CompilationResult:
    behaviors: list[Behavior] = list(workload.extra_behaviors)
    capsules: list[AgentCapsule] = []
    edge_map: dict[int, list[int]] = {}
    for source, target in workload.unconditional_edges:
        edge_map.setdefault(source, []).append(target)
    for index, agent in enumerate(workload.agents):
        name, instructions, tools, handoffs, input_guards, output_guards = _agent_fields(agent, workload.framework)
        dynamic = callable(instructions)
        behaviors.append(Behavior(f"{name}:instructions", "instructions",
                                  Disposition.UNSUPPORTED if dynamic else Disposition.COMPILED,
                                  "arbitrary dynamic callback" if dynamic else "stored as private instruction handle"))
        behaviors.append(Behavior(f"{name}:model", "llm", Disposition.SHARED_PRIMITIVE,
                                  "one shared model invocation through the common ABI"))
        rows = [ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label=f"{name}:llm")]
        state = 1
        for tool_index, tool in enumerate(tools):
            tool_name = _tool_name(tool)
            behaviors.append(Behavior(f"{name}:tool:{tool_name}", "tool", Disposition.SHARED_PRIMITIVE,
                                      "tool work remains behind ToolExecutionAdapter"))
            rows.append(ControlRow(Opcode.TOOL, ControlEvent.MODEL_ACTION, state, state + 1,
                                   target_handle=instruction_handle(tool_name), label=tool_name))
            state += 1
        targets = list(edge_map.get(index, []))
        for handoff in handoffs:
            target_name = str(getattr(handoff, "agent_name", None) or getattr(handoff, "name", "handoff"))
            target = next((i for i, item in enumerate(workload.agents)
                           if str(getattr(item, "name", "")) == target_name), 0)
            targets.append(target)
        for target in targets:
            behaviors.append(Behavior(f"{name}:handoff:{target}", "handoff", Disposition.COMPILED,
                                      "logical id transition in the common executor"))
            rows.append(ControlRow(Opcode.HANDOFF, ControlEvent.HANDOFF_REQUEST, state, 0,
                                   target_handle=base_agent_id + target, label=f"handoff:{target}"))
            state += 1
        for guard in input_guards + output_guards:
            guard_name = getattr(guard, "name", type(guard).__name__)
            behaviors.append(Behavior(f"{name}:guard:{guard_name}", "policy_callback",
                                      Disposition.UNSUPPORTED, "arbitrary native callback is not compiled"))
        rows.append(ControlRow(Opcode.RETURN, ControlEvent.DONE, state, state, label=f"{name}:return"))
        behaviors.append(Behavior(f"{name}:return", "termination", Disposition.COMPILED,
                                  "fixed RETURN transition"))
        source_digest = f"{workload.framework}|{workload.source}|{name}|{len(tools)}|{len(targets)}"
        capsules.append(AgentCapsule(base_agent_id + index, instruction_handle(str(instructions)),
                                     1 if workload.framework == "OpenAI Agents SDK" else 2,
                                     tuple(rows), source_digest))
    for source, target in workload.conditional_edges:
        behaviors.append(Behavior(f"conditional:{source}->{target}", "conditional_edge",
                                  Disposition.UNSUPPORTED, "arbitrary Python predicate; no declarative ABI"))
    for source, targets in workload.fanout_edges:
        behaviors.append(Behavior(f"fanout:{source}->{targets}", "fanout",
                                  Disposition.UNSUPPORTED,
                                  "parallel multi-agent native execution violates the one-heavy-op profile"))
    return CompilationResult(workload.name, workload.framework, workload.source, tuple(capsules),
                             tuple(behaviors), tuple(workload.native_object_types))

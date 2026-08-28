from __future__ import annotations

from dataclasses import dataclass

from .compiler import FrameworkWorkload, _agent_fields, _tool_name
from .ir_v2 import AgentProgramV2, ProgramBundleV2, private_handle


@dataclass(frozen=True)
class V2CompileAudit:
    workload: str
    framework: str
    source: str
    agents: int
    tools: int
    handoffs: int
    agent_tools: int
    dynamic_instruction_callbacks: int
    executable: bool
    unsupported_reasons: tuple[str, ...]


@dataclass(frozen=True)
class V2CompilationResult:
    bundle: ProgramBundleV2
    audit: V2CompileAudit


def compile_workload_v2(workload: FrameworkWorkload, base_agent_id: int,
                        *, max_model_rounds: int = 8) -> V2CompilationResult:
    names = [str(getattr(agent, "name", None) or getattr(agent, "id", f"agent-{index}"))
             for index, agent in enumerate(workload.agents)]
    name_to_id = {name: base_agent_id + index for index, name in enumerate(names)}
    static_edges: dict[int, list[int]] = {}
    for source, target in workload.unconditional_edges:
        static_edges.setdefault(source, []).append(target)
    programs: list[AgentProgramV2] = []
    dynamic = 0
    unsupported: list[str] = []
    tool_total = 0
    handoff_total = 0
    agent_tool_total = 0
    for index, agent in enumerate(workload.agents):
        name, instructions, tools, handoffs, input_guards, output_guards = _agent_fields(agent, workload.framework)
        if callable(instructions):
            dynamic += 1
            unsupported.append(f"{name}: arbitrary dynamic instructions")
        if input_guards or output_guards:
            unsupported.append(f"{name}: arbitrary guardrail/middleware callbacks")
        tool_handles: dict[str, int] = {}
        agent_tool_targets: dict[str, int] = {}
        for tool in tools:
            tool_name = _tool_name(tool)
            if bool(getattr(tool, "_is_agent_tool", False)):
                target = getattr(tool, "_agent_instance", None)
                target_name = str(getattr(target, "name", ""))
                if target_name in name_to_id:
                    agent_tool_targets[tool_name] = name_to_id[target_name]
                    agent_tool_total += 1
                else:
                    unsupported.append(f"{name}: unresolved Agent-as-Tool target {target_name or '<unknown>'}")
            else:
                tool_handles[tool_name] = private_handle("tool", tool_name)
            tool_total += 1
        targets: dict[str, int] = {}
        for target_index in static_edges.get(index, []):
            targets[names[target_index]] = base_agent_id + target_index
        for handoff in handoffs:
            target_name = str(getattr(handoff, "agent_name", None) or getattr(handoff, "name", "handoff"))
            if target_name in name_to_id:
                targets[target_name] = name_to_id[target_name]
            else:
                unsupported.append(f"{name}: unresolved handoff target {target_name}")
        handoff_total += len(targets)
        programs.append(AgentProgramV2(
            base_agent_id + index, name, private_handle("instructions", str(instructions)),
            tool_handles, targets, max_model_rounds, agent_tool_targets,
        ))
    if workload.conditional_edges:
        unsupported.append("arbitrary conditional edges are not part of the core semantic repair")
    if workload.fanout_edges:
        unsupported.append("fan-out/fan-in is not part of the core semantic repair")
    bundle = ProgramBundleV2(workload.name, workload.framework, workload.source, tuple(programs))
    audit = V2CompileAudit(workload.name, workload.framework, workload.source, len(programs),
                           tool_total, handoff_total, agent_tool_total, dynamic,
                           not unsupported, tuple(unsupported))
    return V2CompilationResult(bundle, audit)

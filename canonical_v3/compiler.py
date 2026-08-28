from __future__ import annotations

from dataclasses import dataclass

from agent_control_virtualization.compiler_v2 import V2CompilationResult
from agent_control_virtualization.ir import (AgentCapsule, ControlEvent,
                                             ControlRow, Opcode)
from privacy_kernel.control import OperationClass


@dataclass(frozen=True)
class CanonicalKernelCompilation:
    """Executable lowering for the currently validated one-Tool E2E stratum."""

    capsules: dict[int, AgentCapsule]
    initial_agent_id: int
    provider_by_handle: dict[int, tuple[int, OperationClass]]
    tool_name_by_handle: dict[int, str]
    source: str
    support_stratum: str


def lower_single_tool_agent(compilation: V2CompilationResult, *,
                            provider_code: int = 7,
                            operation_class: OperationClass = OperationClass.READ_ONLY_TOOL,
                            runtime_profile: int = 3) -> CanonicalKernelCompilation:
    """Lower one executable native Agent to MODEL/TOOL/MODEL/RETURN.

    Unsupported shapes fail rather than being approximated. This adapter does
    not increase the corpus-wide IR-v2 executable-support count by itself.
    """

    if not compilation.audit.executable:
        raise ValueError("native workload contains unsupported IR-v2 behavior")
    if len(compilation.bundle.agents) != 1:
        raise ValueError("canonical single-Tool adapter requires exactly one Agent")
    program = compilation.bundle.agents[0]
    if len(program.tool_handles) != 1 or program.handoff_targets:
        raise ValueError("canonical adapter supports exactly one Tool and no handoff")
    tool_name, tool_handle = next(iter(program.tool_handles.items()))
    rows = (
        ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label="model"),
        ControlRow(Opcode.TOOL, ControlEvent.MODEL_ACTION, 1, 2,
                   target_handle=tool_handle, label=tool_name),
        ControlRow(Opcode.LLM, ControlEvent.TOOL_RESULT, 2, 3, label="model-resume"),
        ControlRow(Opcode.RETURN, ControlEvent.DONE, 3, 3, label="return"),
    )
    capsule = AgentCapsule(
        program.logical_agent_id, program.instruction_handle, runtime_profile,
        rows, f"IR-v2|{compilation.bundle.framework}|{compilation.bundle.source}|{program.name}",
    )
    return CanonicalKernelCompilation(
        {program.logical_agent_id: capsule}, program.logical_agent_id,
        {tool_handle: (provider_code, operation_class)}, {tool_handle: tool_name},
        compilation.bundle.source, "NATIVE_SINGLE_TOOL_MODEL_TOOL_MODEL",
    )

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from agent_control_virtualization.compiler import FrameworkWorkload
from agent_control_virtualization.compiler_v2 import compile_workload_v2
from canonical_v3.compiler import lower_single_tool_agent
from canonical_v3.runner import run_canonical_gateway
from privacy_kernel.control import ControlKernel
from privacy_kernel.lookup import SimplePIRLookupSchedule, write_capsule_registry
from privacy_kernel.protocol import CanonicalProfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results_canonical_v3" / "linux_e2e_read_only"


def _native_workload() -> FrameworkWorkload:
    from agents import Agent, function_tool

    def local_lookup(topic: str) -> str:
        return f"synthetic:{topic}"

    tool = function_tool(local_lookup, name_override="READ_ONLY_TOOL",
                         description_override="Read a synthetic local record.")
    agent = Agent(
        name="Canonical native read Agent",
        instructions="Use the local read-only Tool and then return its result.",
        tools=[tool],
    )
    return FrameworkWorkload(
        "canonical-native-read", "OpenAI Agents SDK",
        "external_stage10/openai-agents-python/examples/basic/tools.py", [agent],
        native_object_types=["agents.agent.Agent", "agents.tool.FunctionTool"],
    )


def _profile() -> CanonicalProfile:
    return CanonicalProfile("CANONICAL_V3_LINUX_E2E", 1024, 3, 6,
                            40_000_000, 40_000_000, 8_000_000,
                            350_000_000, 60_000_000)


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    workload = _native_workload()
    ir_v2 = compile_workload_v2(workload, 137, max_model_rounds=2)
    lowered = lower_single_tool_agent(ir_v2)
    registry = OUTPUT / "registry_1000.bin"
    registry_sha256 = write_capsule_registry(registry, 1000, lowered.capsules)
    lookup = SimplePIRLookupSchedule(ROOT, registry, 1000, OUTPUT / "pir", (997, 998, 999))
    slots, pir_audit = lookup.execute([lowered.initial_agent_id, None, None])

    kernel = ControlKernel({}, lowered.initial_agent_id,
                           lowered.provider_by_handle, lowered.tool_name_by_handle)
    kernel.state.pending_lookup = lowered.initial_agent_id
    kernel.install_capsule(slots[0].capsule)
    gateway = run_canonical_gateway(ROOT, OUTPUT / "gateway", _profile(), kernel)
    summary = {
        "native_framework": workload.framework,
        "native_source": workload.source,
        "native_object_types": workload.native_object_types,
        "compiler_audit": asdict(ir_v2.audit),
        "support_stratum": lowered.support_stratum,
        "registry_records": 1000,
        "registry_sha256": registry_sha256,
        "real_pir": asdict(pir_audit),
        "gateway": gateway,
        "result_fed_back_to_control": kernel.state.returned,
        "model_context": kernel.state.model_context,
        "tool_results": kernel.state.tool_results,
        "sanitized_final_result": kernel.state.sanitized_result.decode("utf-8"),
        "failure_class": kernel.state.failure_class,
    }
    (OUTPUT / "e2e_result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from agents import Agent, RunConfig, Runner, function_tool
from agents.testing import ScriptedModel

from stage12_final_p0.workload import PublicTask
from stage13_timing_repair.driver import run_runtime
from stage13_timing_repair.egress import PersistentEgressShaper
from stage13_timing_repair.runtime_common import WorkResult, run_boundary_episode


RUNTIME="OpenAI Agents SDK"
COMMIT="a40ae9803e6b7a79faa246293f56adb100d5868b"


def _call(task: PublicTask) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(type="function_call",name="execute_public_task",call_id=f"s13-{task.workload_id}",
        arguments=json.dumps({"task_id":task.workload_id,"effect_type":task.effect_type,
                              "arguments_json":task.effect_arguments_json},sort_keys=True))


def _final(task: PublicTask) -> ResponseOutputMessage:
    return ResponseOutputMessage(id=f"s13-final-{task.workload_id}",type="message",role="assistant",status="completed",
        content=[ResponseOutputText(text="completed",type="output_text",annotations=[],logprobs=[])])


async def episode(task: PublicTask, family: str, branch: int, mode: str, delta_ms: float,
                  frame_bytes: int, seed: int, shaper: PersistentEgressShaper) -> dict[str,Any]:
    del seed
    proposals=[]
    permissions={task.workload_id} if not branch or family!="AUTHORIZATION" else set()
    histories={task.workload_id} if not branch or family!="PROVENANCE_HISTORY" else set()

    @function_tool(name_override="execute_public_task",needs_approval=True)
    def execute_public_task(task_id: str,effect_type: str,arguments_json: str) -> str:
        proposals.append({"task_id":task_id,"effect_type":effect_type,"arguments_json":arguments_json})
        return "proposal_prepared"

    model=ScriptedModel([[_call(task)],[_final(task)]])
    agent=Agent(name="Stage13Runtime2",model=model,tools=[execute_public_task])
    config=RunConfig(tracing_disabled=True)
    initial=await Runner.run(agent,task.public_task,run_config=config)
    if len(initial.interruptions)!=1 or proposals: raise AssertionError("native pending setup failed")
    state=initial.to_state()
    if task.workload_id in permissions: state.approve(initial.interruptions[0])
    holder: dict[str,Any]={"state":state,"interruption":None}

    async def native_step() -> WorkResult:
        continued=await Runner.run(agent,holder["state"],run_config=config)
        holder["state"]=continued.to_state(); holder["interruption"]=continued.interruptions[0] if continued.interruptions else None
        try: raw=len(holder["state"].to_string().encode())
        except Exception: raw=len(str(continued.final_output).encode())+256
        return WorkResult(raw,bool(proposals),bool(continued.interruptions))

    async def rebuild_history() -> WorkResult:
        hashlib.sha256((task.workload_id+task.effect_type).encode()).digest(); histories.add(task.workload_id)
        return WorkResult(448)

    async def after_step(value: WorkResult) -> None:
        del value
        interruption=holder.get("interruption")
        if interruption is not None:
            holder["state"].approve(interruption); holder["interruption"]=None
        else:
            await asyncio.sleep(0)

    steps=[]
    if family=="PROVENANCE_HISTORY" and task.workload_id not in histories: steps.append(rebuild_history)
    steps.append(native_step)
    if family=="AUTHORIZATION" and task.workload_id not in permissions: steps.append(native_step)
    intended={"task_id":task.workload_id,"effect_type":task.effect_type,"arguments_json":task.effect_arguments_json}
    result=await run_boundary_episode(shaper=shaper,mode=mode,horizon=5,delta_ms=delta_ms,
        frame_bytes=frame_bytes,steps=steps,after_step=after_step,intended_effect=intended)
    model.assert_complete()
    result.update({"runtime_commit":COMMIT,"family":family,"branch":branch,
        "authorization_preserved":result["success"],"effect_equivalent":result["effect"]==intended if result["success"] else False,
        "state_preserved":task.workload_id in histories,"final_result":"completed" if result["success"] else "overflow"})
    return result


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--workload",type=Path,required=True);parser.add_argument("--results",type=Path,required=True)
    args=parser.parse_args();asyncio.run(run_runtime(RUNTIME,episode,args.workload,args.results))


if __name__=="__main__": main()


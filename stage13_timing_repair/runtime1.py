from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections.abc import Awaitable, MutableSequence
from pathlib import Path
from typing import Any

from agent_framework import (Agent,AgentSession,BaseChatClient,ChatResponse,Content,FunctionInvocationLayer,
    Message,ToolApprovalMiddleware,create_always_approve_tool_response,tool)

from stage12_final_p0.workload import PublicTask
from stage13_timing_repair.driver import run_runtime
from stage13_timing_repair.egress import PersistentEgressShaper
from stage13_timing_repair.runtime_common import WorkResult, run_boundary_episode


RUNTIME="Microsoft Agent Framework"
COMMIT="af461de51da16f5cb800ff7febc0f8f96355607a"


class DeterministicClient(FunctionInvocationLayer,BaseChatClient):
    def __init__(self)->None: super().__init__(middleware=[]);self.responses=[]
    def _inner_get_response(self,*,messages:MutableSequence[Message],stream:bool,options:dict[str,Any],**kwargs:Any)->Awaitable[ChatResponse]:
        del messages,stream,options,kwargs
        async def get()->ChatResponse:
            if not self.responses: raise RuntimeError("response queue exhausted")
            return self.responses.pop(0)
        return get()
    def _inner_get_streaming_response(self,**kwargs:Any)->Any: raise NotImplementedError


def _response(contents:list[Content]|list[str])->ChatResponse: return ChatResponse(messages=Message(role="assistant",contents=contents))
def _call(task:PublicTask,call_id:str)->Content:
    return Content.from_function_call(call_id=call_id,name="execute_public_task",arguments=json.dumps(
        {"task_id":task.workload_id,"effect_type":task.effect_type,"arguments_json":task.effect_arguments_json},sort_keys=True))
def _encoded(value:Any)->int:
    if hasattr(value,"to_dict"):value=value.to_dict()
    return len(json.dumps(value,sort_keys=True,default=str,separators=(",",":")).encode())


async def episode(task:PublicTask,family:str,branch:int,mode:str,delta_ms:float,frame_bytes:int,
                  seed:int,shaper:PersistentEgressShaper)->dict[str,Any]:
    proposals=[];permissions={task.workload_id} if not branch or family!="AUTHORIZATION" else set()
    histories={task.workload_id} if not branch or family!="PROVENANCE_HISTORY" else set()

    @tool(name="execute_public_task",approval_mode="always_require")
    def execute_public_task(task_id:str,effect_type:str,arguments_json:str)->str:
        proposals.append({"task_id":task_id,"effect_type":effect_type,"arguments_json":arguments_json});return "proposal_prepared"

    client=DeterministicClient();agent=Agent(client=client,tools=[execute_public_task],middleware=[ToolApprovalMiddleware()])
    session=AgentSession(session_id=f"s13-{seed}")
    if task.workload_id in permissions:
        client.responses=[_response([_call(task,"warmup")])];first=await agent.run("warmup",session=session)
        client.responses=[_response(["warmup complete"])];await agent.run(create_always_approve_tool_response(first.user_input_requests[0]),session=session)
        proposals.clear()
    client.responses=[_response([_call(task,"measured")])]
    if task.workload_id in permissions: client.responses.append(_response(["completed"]))
    holder:dict[str,Any]={"request":None}

    async def native_step()->WorkResult:
        if holder.get("request") is None:value=await agent.run(task.public_task,session=session)
        else:value=await agent.run(create_always_approve_tool_response(holder.pop("request")),session=session)
        if value.user_input_requests:holder["request"]=value.user_input_requests[0]
        return WorkResult(_encoded(value),bool(proposals),bool(value.user_input_requests))
    async def rebuild_history()->WorkResult:
        hashlib.sha256((task.workload_id+task.effect_type).encode()).digest();histories.add(task.workload_id);return WorkResult(448)
    async def after_step(value:WorkResult)->None:
        del value
        if holder.get("request") is not None:client.responses=[_response(["completed"])]
        else:await asyncio.sleep(0)

    steps=[]
    if family=="PROVENANCE_HISTORY" and task.workload_id not in histories:steps.append(rebuild_history)
    steps.append(native_step)
    if family=="AUTHORIZATION" and task.workload_id not in permissions:steps.append(native_step)
    intended={"task_id":task.workload_id,"effect_type":task.effect_type,"arguments_json":task.effect_arguments_json}
    result=await run_boundary_episode(shaper=shaper,mode=mode,horizon=5,delta_ms=delta_ms,frame_bytes=frame_bytes,
        steps=steps,after_step=after_step,intended_effect=intended)
    result.update({"runtime_commit":COMMIT,"family":family,"branch":branch,"authorization_preserved":result["success"],
        "effect_equivalent":result["effect"]==intended if result["success"] else False,
        "state_preserved":task.workload_id in histories,"final_result":"completed" if result["success"] else "overflow"})
    return result


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--workload",type=Path,required=True);parser.add_argument("--results",type=Path,required=True)
    args=parser.parse_args();asyncio.run(run_runtime(RUNTIME,episode,args.workload,args.results))


if __name__=="__main__":main()


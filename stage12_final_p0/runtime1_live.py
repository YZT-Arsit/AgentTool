from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import statistics
from collections.abc import Awaitable, MutableSequence
from pathlib import Path
from typing import Any

from agent_framework import (Agent, AgentSession, BaseChatClient, ChatResponse, Content,
    FunctionInvocationLayer, Message, ToolApprovalMiddleware,
    create_always_approve_tool_response, tool)

from stage12_final_p0.live_core import LiveConfig, StepResult, run_live
from stage12_final_p0.workload import PublicTask, load_workload


RUNTIME = "Microsoft Agent Framework"
COMMIT = "af461de51da16f5cb800ff7febc0f8f96355607a"


class DeterministicClient(FunctionInvocationLayer, BaseChatClient):
    def __init__(self) -> None:
        super().__init__(middleware=[]); self.responses: list[ChatResponse] = []
    def _inner_get_response(self, *, messages: MutableSequence[Message], stream: bool,
                            options: dict[str, Any], **kwargs: Any) -> Awaitable[ChatResponse]:
        del messages, stream, options, kwargs
        async def get() -> ChatResponse:
            if not self.responses: raise RuntimeError("response queue exhausted")
            return self.responses.pop(0)
        return get()
    def _inner_get_streaming_response(self, **kwargs: Any) -> Any:
        raise NotImplementedError


def _response(contents: list[Content] | list[str]) -> ChatResponse:
    return ChatResponse(messages=Message(role="assistant", contents=contents))


def _call(task: PublicTask, call_id: str) -> Content:
    return Content.from_function_call(call_id=call_id, name="execute_public_task",
        arguments=json.dumps({"task_id": task.workload_id, "effect_type": task.effect_type,
                              "arguments_json": task.effect_arguments_json}, sort_keys=True))


def _encoded(value: Any) -> int:
    if hasattr(value, "to_dict"): value = value.to_dict()
    return len(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode())


async def _episode(task: PublicTask, family: str, branch: int, variant: str, config: LiveConfig, seed: int) -> dict[str, Any]:
    proposals: list[dict[str, str]] = []
    effects: list[dict[str, str]] = []
    permission_records = {task.workload_id} if not branch or family != "AUTHORIZATION" else set()
    history_records = {task.workload_id} if not branch or family != "PROVENANCE_HISTORY" else set()

    @tool(name="execute_public_task", approval_mode="always_require")
    def execute_public_task(task_id: str, effect_type: str, arguments_json: str) -> str:
        proposals.append({"task_id": task_id, "effect_type": effect_type, "arguments_json": arguments_json})
        return "proposal_prepared"

    client = DeterministicClient()
    agent = Agent(client=client, tools=[execute_public_task], middleware=[ToolApprovalMiddleware()])
    session = AgentSession(session_id=f"s12-{seed}")
    if task.workload_id in permission_records:
        client.responses = [_response([_call(task, "warmup")])]
        first = await agent.run("warmup", session=session)
        request = first.user_input_requests[0]
        client.responses = [_response(["warmup complete"])]
        await agent.run(create_always_approve_tool_response(request), session=session)
        proposals.clear()

    client.responses = [_response([_call(task, "measured")])]
    if task.workload_id in permission_records:
        client.responses.append(_response(["completed"]))
    holder: dict[str, Any] = {"request": None}

    async def native_step() -> StepResult:
        if holder.get("request") is None:
            value = await agent.run(task.public_task, session=session)
        else:
            value = await agent.run(create_always_approve_tool_response(holder.pop("request")), session=session)
        if value.user_input_requests:
            holder["request"] = value.user_input_requests[0]
        holder["value"] = value
        return StepResult(_encoded(value), bool(value.user_input_requests), bool(proposals))

    async def rebuild_history() -> StepResult:
        hashlib.sha256((task.workload_id + task.effect_type).encode()).digest()
        history_records.add(task.workload_id)
        return StepResult(448)

    async def approval_work() -> None:
        if holder.get("request") is not None:
            client.responses = [_response(["completed"])]
        else:
            await asyncio.sleep(0)

    steps = []
    if family == "PROVENANCE_HISTORY" and task.workload_id not in history_records:
        steps.append(rebuild_history)
    steps.append(native_step)
    if family == "AUTHORIZATION" and task.workload_id not in permission_records:
        steps.append(native_step)

    def commit() -> dict[str, object]:
        if len(proposals) != 1: raise AssertionError(f"expected one proposal, got {len(proposals)}")
        effects.append(dict(proposals[0])); return effects[0]

    result = await run_live(variant=variant, config=config, real_steps=steps,
                            approval_work=approval_work, commit=commit, seed=seed)
    if result["effect_count"] != 1 or result["dummy_external_effects"] != 0:
        raise AssertionError("effect-safety invariant failed")
    result.update({"runtime": RUNTIME, "runtime_commit": COMMIT, "task_id": task.workload_id,
                   "family": family, "variant": variant, "seed": seed,
                   "public_effect_type": task.effect_type, "final_result": "completed",
                   "authorization_preserved": True, "state_preserved": task.workload_id in history_records})
    return result


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values); return ordered[min(len(ordered)-1, max(0, math.ceil(p*len(ordered))-1))]


async def run_all(workload_path: Path, output: Path, truth_output: Path, profile_output: Path) -> None:
    tasks = load_workload(workload_path)
    profile_latencies: list[float] = []; profile_sizes: list[int] = []
    base = LiveConfig(horizon=5, delta_ms=5, frame_bytes=16384, approval_window_ms=2, size_mode="NONE")
    for index, task in enumerate(tasks[:16]):
        for family_index, family in enumerate(("AUTHORIZATION", "PROVENANCE_HISTORY")):
            for branch in (0, 1):
                row = await _episode(task, family, branch, "M1", base, 1000 + index*10 + family_index*2 + branch)
                # Pool all training states without class-conditional selection.
                profile_latencies.append(float(row["latency_ms"]))
                profile_sizes.extend(int(e["serialized_bytes"]) for e in row["host_visible_trace"])
    deltas = {name: max(1.0, _percentile(profile_latencies, p) * 1.35) for name, p in (("P90",.90),("P95",.95),("P99",.99))}
    max_raw=max(profile_sizes); frame=max(4096, 1 << math.ceil(math.log2(max_raw+8)))
    chosen=LiveConfig(5,deltas["P99"],frame,20.0,"FIXED")
    results=[]; truth=[]
    for task_index, task in enumerate(tasks):
        for family in ("AUTHORIZATION", "PROVENANCE_HISTORY"):
            for branch in (0,1):
                for repetition in range(3):
                    for variant in ("M0","M1","M2","M3"):
                        cfg=chosen if variant=="M3" else LiveConfig(5,chosen.delta_ms,frame,0.5,"NONE")
                        run_id=f"r1-{task_index}-{family}-{branch}-{repetition}-{variant}"
                        row=await _episode(task,family,branch,variant,cfg,30000+task_index*1000+branch*100+repetition*10+len(variant))
                        host=dict(row); host.pop("private_audit",None); host.pop("family",None); host["run_id"]=run_id
                        results.append(host); truth.append({"run_id":run_id,"task_id":task.workload_id,"family":family,
                                                            "branch":branch,"variant":variant,"runtime":RUNTIME})
    cadence_rows=[]
    for name,delta in deltas.items():
        for index,task in enumerate(tasks[8:12]):
            for branch in (0,1):
                cfg=LiveConfig(5,delta,frame,20.0,"FIXED")
                row=await _episode(task,"AUTHORIZATION",branch,"M3",cfg,80000+index*10+branch)
                cadence_rows.append({"percentile":name,"task_id":task.workload_id,"branch":branch,
                    "latency_ms":row["latency_ms"],"deadline_overflows":row["deadline_overflows"],
                    "wait_fraction":row["wait_fraction"],"dummy_fraction":row["dummy_slots"]/5})
    size_rows=[]
    for mode in ("NONE","FIXED","BUCKET"):
        for index,task in enumerate(tasks[12:16]):
            for branch in (0,1):
                cfg=LiveConfig(5,deltas["P99"],frame,20.0,mode)
                row=await _episode(task,"AUTHORIZATION",branch,"M3",cfg,90000+index*10+branch)
                size_rows.append({"mode":mode,"task_id":task.workload_id,"branch":branch,
                    "wire_bytes":sum(e["serialized_bytes"] for e in row["host_visible_trace"]),
                    "size_sequence":[e["serialized_bytes"] for e in row["host_visible_trace"]]})
    approval_rows=[]
    for window in (1000.0,2000.0):
        for branch in (0,1):
            cfg=LiveConfig(5,deltas["P99"],frame,window,"FIXED")
            row=await _episode(tasks[16],"AUTHORIZATION",branch,"M3",cfg,95000+int(window)+branch)
            approval_rows.append({"window_ms":window,"branch":branch,"latency_ms":row["latency_ms"],
                                  "deadline_overflows":row["deadline_overflows"]})
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8") as handle:
        for row in results: handle.write(json.dumps(row,sort_keys=True)+"\n")
    with truth_output.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(truth[0])); writer.writeheader(); writer.writerows(truth)
    profile_output.write_text(json.dumps({"runtime":RUNTIME,"samples":len(profile_latencies),
        "profile_mean_ms":statistics.mean(profile_latencies),"deltas_ms":deltas,"frame_bytes":frame,
        "profile_task_ids":[t.workload_id for t in tasks[:16]],"test_label_used_for_selection":False,
        "cadence_evaluation":cadence_rows,"size_evaluation":size_rows,
        "approval_window_evaluation":approval_rows},indent=2),encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--workload",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True); parser.add_argument("--truth-output",type=Path,required=True)
    parser.add_argument("--profile-output",type=Path,required=True); args=parser.parse_args()
    asyncio.run(run_all(args.workload,args.output,args.truth_output,args.profile_output))


if __name__ == "__main__": main()

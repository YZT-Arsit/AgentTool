from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText
from agents import Agent, RunConfig, Runner, function_tool
from agents.testing import ScriptedModel

from stage12_final_p0.live_core import LiveConfig, StepResult, run_live
from stage12_final_p0.workload import PublicTask, load_workload


RUNTIME = "OpenAI Agents SDK"
COMMIT = "a40ae9803e6b7a79faa246293f56adb100d5868b"


def _call(task: PublicTask) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(
        type="function_call", name="execute_public_task", call_id=f"s12-{task.workload_id}",
        arguments=json.dumps({"task_id": task.workload_id, "effect_type": task.effect_type,
                              "arguments_json": task.effect_arguments_json}, sort_keys=True),
    )


def _final(task: PublicTask) -> ResponseOutputMessage:
    return ResponseOutputMessage(
        id=f"s12-final-{task.workload_id}", type="message", role="assistant", status="completed",
        content=[ResponseOutputText(text="completed", type="output_text", annotations=[], logprobs=[])],
    )


async def _episode(task: PublicTask, family: str, branch: int, variant: str, config: LiveConfig, seed: int) -> dict[str, Any]:
    proposals: list[dict[str, str]] = []
    effects: list[dict[str, str]] = []
    permission_records = {task.workload_id} if not branch or family != "AUTHORIZATION" else set()
    history_records = {task.workload_id} if not branch or family != "PROVENANCE_HISTORY" else set()

    @function_tool(name_override="execute_public_task", needs_approval=True)
    def execute_public_task(task_id: str, effect_type: str, arguments_json: str) -> str:
        proposals.append({"task_id": task_id, "effect_type": effect_type, "arguments_json": arguments_json})
        return "proposal_prepared"

    model = ScriptedModel([[_call(task)], [_final(task)]])
    agent = Agent(name="Stage12Runtime2", model=model, tools=[execute_public_task])
    config_sdk = RunConfig(tracing_disabled=True)
    initial = await Runner.run(agent, task.public_task, run_config=config_sdk)
    if len(initial.interruptions) != 1 or proposals:
        raise AssertionError("native pending approval setup failed")
    state = initial.to_state()
    if task.workload_id in permission_records:
        state.approve(initial.interruptions[0])
    holder: dict[str, Any] = {"state": state, "interruption": None}

    async def native_step() -> StepResult:
        continued = await Runner.run(agent, holder["state"], run_config=config_sdk)
        holder["continued"] = continued
        holder["state"] = continued.to_state()
        holder["interruption"] = continued.interruptions[0] if continued.interruptions else None
        try:
            raw = len(holder["state"].to_string().encode())
        except Exception:
            raw = len(json.dumps({"output": str(continued.final_output), "interruptions": len(continued.interruptions)}).encode())
        return StepResult(raw, bool(continued.interruptions), bool(proposals))

    async def rebuild_history() -> StepResult:
        # Existing trusted mediation semantics: reconstruct an absent provenance
        # record from the public reference-action prefix, then persist it.
        hashlib.sha256((task.workload_id + task.effect_type).encode()).digest()
        history_records.add(task.workload_id)
        return StepResult(448, False, False)

    async def approval_work() -> None:
        interruption = holder.get("interruption")
        if interruption is not None:
            holder["state"].approve(interruption)
            holder["interruption"] = None
        else:
            await asyncio.sleep(0)

    steps = []
    if family == "PROVENANCE_HISTORY" and task.workload_id not in history_records:
        steps.append(rebuild_history)
    steps.append(native_step)
    if family == "AUTHORIZATION" and task.workload_id not in permission_records:
        steps.append(native_step)

    def commit() -> dict[str, object]:
        if len(proposals) != 1:
            raise AssertionError(f"expected one authorized proposal, got {len(proposals)}")
        effects.append(dict(proposals[0]))
        return effects[0]

    result = await run_live(variant=variant, config=config, real_steps=steps,
                            approval_work=approval_work, commit=commit, seed=seed)
    if result["effect_count"] != 1 or result["dummy_external_effects"] != 0:
        raise AssertionError("effect-safety invariant failed")
    model.assert_complete()
    result.update({"runtime": RUNTIME, "runtime_commit": COMMIT, "task_id": task.workload_id,
                   "family": family, "variant": variant, "seed": seed,
                   "public_effect_type": task.effect_type, "final_result": "completed",
                   "authorization_preserved": True, "state_preserved": task.workload_id in history_records})
    return result


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(p * len(ordered)) - 1))]


async def run_all(workload_path: Path, output: Path, truth_output: Path, profile_output: Path) -> None:
    tasks = load_workload(workload_path)
    profile_latencies: list[float] = []
    profile_sizes: list[int] = []
    base = LiveConfig(horizon=5, delta_ms=5, frame_bytes=16384, approval_window_ms=2, size_mode="NONE")
    for index, task in enumerate(tasks[:16]):
        for family_index, family in enumerate(("AUTHORIZATION", "PROVENANCE_HISTORY")):
            for branch in (0, 1):
                row = await _episode(task, family, branch, "M1", base, 1000 + index * 10 + family_index * 2 + branch)
                profile_latencies.append(float(row["latency_ms"]))
                profile_sizes.extend(int(e["serialized_bytes"]) for e in row["host_visible_trace"])
    deltas = {name: max(1.0, _percentile(profile_latencies, p) * 1.35) for name, p in (("P90", .90), ("P95", .95), ("P99", .99))}
    max_raw = max(profile_sizes)
    frame = max(4096, 1 << math.ceil(math.log2(max_raw + 8)))
    chosen = LiveConfig(horizon=5, delta_ms=deltas["P99"], frame_bytes=frame,
                        approval_window_ms=20.0, size_mode="FIXED")
    results: list[dict[str, Any]] = []
    truth: list[dict[str, Any]] = []
    for task_index, task in enumerate(tasks):
        for family in ("AUTHORIZATION", "PROVENANCE_HISTORY"):
            for branch in (0, 1):
                for repetition in range(3):
                    for variant in ("M0", "M1", "M2", "M3"):
                        cfg = chosen if variant == "M3" else LiveConfig(horizon=5, delta_ms=chosen.delta_ms,
                            frame_bytes=frame, approval_window_ms=0.5, size_mode="NONE")
                        run_id = f"r2-{task_index}-{family}-{branch}-{repetition}-{variant}"
                        row = await _episode(task, family, branch, variant, cfg, 20000 + task_index * 1000 + branch * 100 + repetition * 10 + len(variant))
                        host = dict(row)
                        host.pop("private_audit", None)
                        host.pop("family", None)
                        host["run_id"] = run_id
                        results.append(host)
                        truth.append({"run_id": run_id, "task_id": task.workload_id, "family": family,
                                      "branch": branch, "variant": variant, "runtime": RUNTIME})
    cadence_rows = []
    for name, delta in deltas.items():
        for index, task in enumerate(tasks[8:12]):
            for branch in (0, 1):
                cfg = LiveConfig(5, delta, frame, 20.0, "FIXED")
                row = await _episode(task, "AUTHORIZATION", branch, "M3", cfg, 80000 + index * 10 + branch)
                cadence_rows.append({"percentile": name, "task_id": task.workload_id, "branch": branch,
                    "latency_ms": row["latency_ms"], "deadline_overflows": row["deadline_overflows"],
                    "wait_fraction": row["wait_fraction"], "dummy_fraction": row["dummy_slots"] / 5})
    size_rows = []
    for mode in ("NONE", "FIXED", "BUCKET"):
        for index, task in enumerate(tasks[12:16]):
            for branch in (0, 1):
                cfg = LiveConfig(5, deltas["P99"], frame, 20.0, mode)
                row = await _episode(task, "AUTHORIZATION", branch, "M3", cfg, 90000 + index * 10 + branch)
                size_rows.append({"mode": mode, "task_id": task.workload_id, "branch": branch,
                    "wire_bytes": sum(e["serialized_bytes"] for e in row["host_visible_trace"]),
                    "size_sequence": [e["serialized_bytes"] for e in row["host_visible_trace"]]})
    approval_rows = []
    for window in (1000.0, 2000.0):
        for branch in (0, 1):
            cfg = LiveConfig(5, deltas["P99"], frame, window, "FIXED")
            row = await _episode(tasks[16], "AUTHORIZATION", branch, "M3", cfg, 95000 + int(window) + branch)
            approval_rows.append({"window_ms": window, "branch": branch, "latency_ms": row["latency_ms"],
                                  "deadline_overflows": row["deadline_overflows"]})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    with truth_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(truth[0]))
        writer.writeheader(); writer.writerows(truth)
    profile_output.write_text(json.dumps({"runtime": RUNTIME, "samples": len(profile_latencies),
        "profile_mean_ms": statistics.mean(profile_latencies), "deltas_ms": deltas,
        "frame_bytes": frame, "profile_task_ids": [task.workload_id for task in tasks[:16]],
        "test_label_used_for_selection": False, "cadence_evaluation": cadence_rows,
        "size_evaluation": size_rows, "approval_window_evaluation": approval_rows}, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--truth-output", type=Path, required=True)
    parser.add_argument("--profile-output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run_all(args.workload, args.output, args.truth_output, args.profile_output))


if __name__ == "__main__":
    main()

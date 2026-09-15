from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v14_provisioned_agents.artifact import ProvisionedAgentArtifactCodec
from v14_provisioned_agents.fixtures import DUMMY_PIR_ROW, SCALE_RECORDS, STORE_EPOCH, functional_artifacts
from v14_provisioned_agents.gateway import run_frozen_v4r8_gateway_artifact_session
from v14_provisioned_agents.loader import AgentLoader
from v14_provisioned_agents.models import ProvisionedAgentArtifactV1
from v14_provisioned_agents.psi import RealLabeledAPSIClient
from v14_provisioned_agents.simplepir import PersistentSimplePIRArtifactClient
from v15b_agent_access.pipeline import AgentAccessProfile, AgentAccessRequest, PipelinedAgentAccessScheduler


BASE_V15B = "2cf835cb1e63e1f6f15bfdb523f563ae8608e868"
APSI_SHA = "fd088edc9a12760b8ba0a7fe86fe31db91f5714c3da8a0bbe74096e6767481e0"
PIR_SHA = "2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b"


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values); position = (len(ordered) - 1) * q
    lo = int(position); hi = min(lo + 1, len(ordered) - 1); weight = position - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--port", type=int, default=12766)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)

    apsi_sender = ROOT / "apsi-build/oae_v14_apsi_sender_service"
    apsi_receiver = ROOT / "apsi-build/oae_v14_apsi_receiver_bridge"
    apsi_db = ROOT / "work/apsi_sender_db.bin"
    simplepir = Path("/root/autodl-tmp/mediation_trace_validation/pir_integration/simplepir_bridge/acv-simplepir-online")
    pir_db = ROOT / "work/provisioned_agent_store_100k_plus_dummy.bin"
    gateway_runner = Path("/root/autodl-tmp/v12_v4r7_smoke_exec/common_action_gateway_v2/bin/canonical-v12-v4r8-timing-runner")
    codec = ProvisionedAgentArtifactCodec((ROOT / "work/artifact_aead_key.private").read_bytes(), STORE_EPOCH)
    profile = AgentAccessProfile("OAE-AGENT-ACCESS-P2-RA4-D350", 3, 350).validate()
    functional = {artifact.canonical_agent_id: artifact for artifact in functional_artifacts()}
    repository_rows = {
        agent_id: codec.encode(artifact) for agent_id, artifact in functional.items()
        if agent_id > SCALE_RECORDS
    }
    freeze = {
        "schema": "AgentTool.V15DUtilitySupplementFreeze/1", "base_v15b": BASE_V15B,
        "repetitions": args.repetitions,
        "workloads": ["UNPROVISIONED_NESTED_AGENT_AS_TOOL", "MIXED_AGENT_LLM_TOOL"],
        "unprovisioned_nested_policy": (
            "Parent miss completes one frozen access/Gateway profile; the causally learned child "
            "re-enters a second unchanged frozen access/Gateway profile."
        ),
        "mixed_policy": (
            "One provisioned parent+child Agent-as-Tool execution plus one unprovisioned ordinary "
            "Agent; deterministic framework model calls and the Agent-as-Tool call are counted."
        ),
        "selection_rule": "all rows included; no retry or replacement",
    }
    (output / "CAMPAIGN_FREEZE.json").write_text(json.dumps(freeze, indent=2) + "\n")
    sender = subprocess.Popen(
        [str(apsi_sender), "--db", str(apsi_db), "--metrics", str(output / "apsi_sender.jsonl"),
         "--port", str(args.port)],
        stdout=(output / "apsi_sender_stdout.txt").open("wb"),
        stderr=(output / "apsi_sender_stderr.txt").open("wb"),
    )
    time.sleep(1)
    rows: list[dict[str, Any]] = []
    try:
        with RealLabeledAPSIClient(
            apsi_receiver, f"tcp://127.0.0.1:{args.port}", expected_sha256=APSI_SHA,
        ) as psi, PersistentSimplePIRArtifactClient(
            simplepir, pir_db, SCALE_RECORDS + 1, output / "simplepir", expected_sha256=PIR_SHA,
        ) as pir:

            def phase(run_id: str, phase_no: int, initial_ids: list[int]) -> dict[str, Any]:
                phase_start = time.monotonic_ns()
                gateway_queue: list[int] = []
                scheduler = PipelinedAgentAccessScheduler(
                    profile, psi, pir, codec, dummy_row=DUMMY_PIR_ROW,
                    gateway_queue=gateway_queue.append,
                )
                request_created: dict[str, int] = {}
                top_ids: list[str] = []
                for index, agent_id in enumerate(initial_ids):
                    request_id = f"{run_id}-P{phase_no}-initial-{index}"
                    request_created[request_id] = phase_start
                    scheduler.enqueue(AgentAccessRequest(request_id, agent_id)); top_ids.append(request_id)
                artifacts: dict[str, ProvisionedAgentArtifactV1] = {}
                ready_ns: dict[str, int] = {}
                pending = []
                queued_nested: set[int] = set()
                lateness: list[float] = []
                origin = time.monotonic_ns() + profile.initial_lead_ms * 1_000_000
                try:
                    for slot in range(4):
                        scheduled = origin + slot * profile.interval_ms * 1_000_000
                        now = time.monotonic_ns()
                        if now < scheduled:
                            time.sleep((scheduled - now) / 1e9)
                        started = time.monotonic_ns()
                        result = scheduler.execute_slot(drain=slot == 3)
                        completed = time.monotonic_ns()
                        lateness.append(max(0, started - scheduled) / 1e6)
                        if result is None:
                            continue
                        if result.artifact is None:
                            pending.append(result); continue
                        artifacts[result.request.request_id] = result.artifact
                        ready_ns[result.request.request_id] = completed
                        for child in result.artifact.sub_agent_ids:
                            if child not in queued_nested:
                                nested_id = f"{run_id}-P{phase_no}-nested-{child}"
                                request_created[nested_id] = completed
                                scheduler.enqueue(AgentAccessRequest(nested_id, child))
                                queued_nested.add(child)
                finally:
                    scheduler.close()
                if len(gateway_queue) > 1:
                    raise RuntimeError("one frozen Gateway profile carries at most one repository artifact")
                gateway_agent = gateway_queue[0] if gateway_queue else None
                gateway = run_frozen_v4r8_gateway_artifact_session(
                    gateway_runner, output / "gateway" / f"{run_id}-P{phase_no}",
                    agent_id=gateway_agent,
                    artifact=repository_rows[gateway_agent] if gateway_agent is not None else None,
                )
                gateway_done = time.monotonic_ns()
                for result in pending:
                    if gateway.artifact is None:
                        raise RuntimeError("Gateway repository retrieval returned no artifact")
                    artifact = codec.decode(gateway.artifact, result.request.agent_id)
                    artifacts[result.request.request_id] = artifact; ready_ns[result.request.request_id] = gateway_done
                conformance = (
                    len(scheduler.public_slots) == 4
                    and all(slot.psi_framed_lengths == (104, 104, 697972, 1579652)
                            and slot.pir_framed_lengths == (36388, 37180)
                            for slot in scheduler.public_slots)
                    and gateway.public_profile["relay_cells"] == 521
                    and gateway.public_profile["public_transcript_complete"] is True
                )
                return {
                    "top_request_ids": top_ids, "artifacts": artifacts,
                    "request_created_ns": request_created, "ready_ns": ready_ns,
                    "gateway_queue": gateway_queue, "nested_ids": sorted(queued_nested),
                    "profile_conformance": conformance, "max_slot_lateness_ms": max(lateness),
                    "gateway_result": gateway.result, "phase_end_ns": gateway_done,
                    "public_slots": [slot.canonical() for slot in scheduler.public_slots],
                }

            run_no = 0
            for repetition in range(1, args.repetitions + 1):
                for framework, base in (("OpenAI", 101), ("Microsoft", 201)):
                    for workload in ("UNPROVISIONED_NESTED_AGENT_AS_TOOL", "MIXED_AGENT_LLM_TOOL"):
                        run_no += 1
                        run_id = f"V15D-SUP-{run_no:03d}-{framework.upper()}-{workload}-R{repetition}"
                        started = time.monotonic_ns()
                        phases: list[dict[str, Any]] = []
                        semantic_outputs: list[str] = []
                        if workload == "UNPROVISIONED_NESTED_AGENT_AS_TOOL":
                            parent_id = 1_000_001 + base; child_id = 1_000_002 + base
                            parent_phase = phase(run_id, 1, [parent_id]); phases.append(parent_phase)
                            parent = next(a for a in parent_phase["artifacts"].values()
                                          if a.canonical_agent_id == parent_id)
                            if tuple(parent.sub_agent_ids) != (child_id,):
                                raise RuntimeError("unprovisioned parent did not authenticate its child AgentID")
                            child_phase = phase(run_id, 2, [child_id]); phases.append(child_phase)
                            child = next(a for a in child_phase["artifacts"].values()
                                         if a.canonical_agent_id == child_id)
                            loaded = AgentLoader().load(parent, (AgentLoader().load(child),))
                            semantic_outputs.append(loaded.run())
                            expected = [parent.runtime_policy["expected_output"]]
                            real_agents, model_calls, tool_calls = 2, 3, 1
                        else:
                            phase_result = phase(run_id, 1, [base + 1, 1_000_000 + base]); phases.append(phase_result)
                            by_agent = {a.canonical_agent_id: a for a in phase_result["artifacts"].values()}
                            parent, child, ordinary = by_agent[base + 1], by_agent[base + 2], by_agent[1_000_000 + base]
                            semantic_outputs.append(AgentLoader().load(parent, (AgentLoader().load(child),)).run())
                            semantic_outputs.append(AgentLoader().load(ordinary).run())
                            expected = [parent.runtime_policy["expected_output"], ordinary.runtime_policy["expected_output"]]
                            real_agents, model_calls, tool_calls = 3, 4, 1
                        completed = time.monotonic_ns()
                        retrievals = [
                            (value - part["request_created_ns"][key]) / 1e6
                            for part in phases for key, value in part["ready_ns"].items()
                        ]
                        overflow = sum(int(p["gateway_result"].get("profile_overflow_events", 0)) for p in phases)
                        silent = sum(int(p["gateway_result"].get("silent_committed_result_losses", 0)) for p in phases)
                        rows.append({
                            "run_id": run_id, "repetition": repetition, "framework": framework,
                            "workload": workload, "public_profile_instances": len(phases),
                            "scheduled_agent_access_slots": 4 * len(phases),
                            "gateway_public_sessions": len(phases),
                            "semantic_success": semantic_outputs == expected,
                            "profile_conformance": all(p["profile_conformance"] for p in phases),
                            "task_latency_ms": (completed - started) / 1e6,
                            "first_agent_retrieval_latency_ms": retrievals[0],
                            "total_agent_resolution_latency_ms": sum(retrievals),
                            "retrieval_latency_p50_ms": percentile(retrievals, .5),
                            "retrieval_latency_p95_ms": percentile(retrievals, .95),
                            "full_public_obligations_wall_ms": (max(p["phase_end_ns"] for p in phases) - started) / 1e6,
                            "retrieval_count": len(retrievals), "overflow_count": overflow,
                            "silent_loss_count": silent, "profile_capacity_failures": 0,
                            "retrieval_failures": 0, "agent_loader_failures": 0,
                            "real_agent_executions": real_agents,
                            "framework_model_invocations": model_calls,
                            "framework_agent_as_tool_invocations": tool_calls,
                            "real_remote_llm_calls": 0, "real_external_tool_api_calls": 0,
                            "dummy_heavy_agent_executions": 0, "dummy_heavy_llm_executions": 0,
                            "dummy_heavy_tool_executions": 0, "semantic_outputs": semantic_outputs,
                            "retrieval_latencies_ms": retrievals,
                        })
                        print(json.dumps({"completed": run_id, "semantic": rows[-1]["semantic_success"],
                                          "profile": rows[-1]["profile_conformance"]}), flush=True)
    finally:
        sender.terminate()
        try:
            sender.wait(timeout=30)
        except subprocess.TimeoutExpired:
            sender.kill(); sender.wait(timeout=10)
    payload = {
        "schema": "AgentTool.V15DUtilitySupplement/1", "base_v15b": BASE_V15B,
        "measured_executions": len(rows), "rows": rows,
    }
    (output / "v15d_utility_supplement_raw.json").write_text(json.dumps(payload, indent=2) + "\n")
    if not all(row["semantic_success"] and row["profile_conformance"] for row in rows):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

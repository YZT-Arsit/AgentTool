from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path("/root/autodl-tmp/v14")
sys.path.insert(0, str(ROOT))

from v14_provisioned_agents.artifact import ProvisionedAgentArtifactCodec
from v14_provisioned_agents.fixtures import (
    DUMMY_PIR_ROW,
    SCALE_RECORDS,
    STORE_EPOCH,
    functional_artifacts,
)
from v14_provisioned_agents.gateway import run_frozen_v4r8_gateway_artifact_session
from v14_provisioned_agents.loader import AgentLoader
from v14_provisioned_agents.models import ProvisionedAgentArtifactV1
from v14_provisioned_agents.psi import RealLabeledAPSIClient
from v14_provisioned_agents.simplepir import PersistentSimplePIRArtifactClient
from v15b_agent_access.pipeline import (
    AgentAccessProfile,
    AgentAccessRequest,
    PipelinedAgentAccessScheduler,
)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    weight = index - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--port", type=int, default=12366)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)

    apsi_sender = ROOT / "apsi-build/oae_v14_apsi_sender_service"
    apsi_receiver = ROOT / "apsi-build/oae_v14_apsi_receiver_bridge"
    apsi_db = ROOT / "work/apsi_sender_db.bin"
    simplepir = Path("/root/autodl-tmp/mediation_trace_validation/pir_integration/simplepir_bridge/acv-simplepir-online")
    pir_db = ROOT / "work/provisioned_agent_store_100k_plus_dummy.bin"
    aead_key = ROOT / "work/artifact_aead_key.private"
    gateway_runner = Path("/root/autodl-tmp/v12_v4r7_smoke_exec/common_action_gateway_v2/bin/canonical-v12-v4r8-timing-runner")

    profile = AgentAccessProfile("OAE-AGENT-ACCESS-P2-RA4-D350", 3, 350).validate()
    codec = ProvisionedAgentArtifactCodec(aead_key.read_bytes(), STORE_EPOCH)
    functional = {a.canonical_agent_id: a for a in functional_artifacts()}
    repository_rows = {
        agent_id: codec.encode(artifact)
        for agent_id, artifact in functional.items()
        if agent_id > SCALE_RECORDS
    }
    specs = []
    for framework, base in (("OpenAI", 101), ("Microsoft", 201)):
        specs.extend(
            [
                (framework, "PROVISIONED_ORDINARY", [base]),
                (framework, "UNPROVISIONED_ORDINARY", [1_000_000 + base]),
                (framework, "NESTED_AGENT_AS_TOOL", [base + 1]),
                (framework, "REPEATED_AGENT", [base, base, base]),
                (framework, "MIXED", [base, 1_000_000 + base]),
                (framework, "IDLE_PROFILE_ONLY", []),
            ]
        )

    sender_metrics = output / "apsi_sender_metrics.jsonl"
    sender = subprocess.Popen(
        [str(apsi_sender), "--db", str(apsi_db), "--metrics", str(sender_metrics), "--port", str(args.port)],
        stdout=(output / "apsi_sender_stdout.txt").open("wb"),
        stderr=(output / "apsi_sender_stderr.txt").open("wb"),
    )
    time.sleep(1)
    rows: list[dict[str, Any]] = []
    try:
        with RealLabeledAPSIClient(
            apsi_receiver,
            f"tcp://127.0.0.1:{args.port}",
            expected_sha256="fd088edc9a12760b8ba0a7fe86fe31db91f5714c3da8a0bbe74096e6767481e0",
        ) as psi, PersistentSimplePIRArtifactClient(
            simplepir,
            pir_db,
            SCALE_RECORDS + 1,
            output / "simplepir",
            expected_sha256="2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b",
        ) as pir:
            run_number = 0
            for repetition in range(1, args.repetitions + 1):
                for framework, workload, initial_ids in specs:
                    run_number += 1
                    run_id = f"V15C-{run_number:03d}-{framework.upper()}-{workload}-R{repetition}"
                    run_dir = output / "gateway" / run_id
                    session_start_ns = time.monotonic_ns()
                    gateway_queue: list[int] = []
                    scheduler = PipelinedAgentAccessScheduler(
                        profile,
                        psi,
                        pir,
                        codec,
                        dummy_row=DUMMY_PIR_ROW,
                        gateway_queue=gateway_queue.append,
                    )
                    request_created_ns: dict[str, int] = {}
                    top_level_request_ids: list[str] = []
                    for index, agent_id in enumerate(initial_ids):
                        request_id = f"{run_id}-initial-{index}"
                        request_created_ns[request_id] = session_start_ns
                        scheduler.enqueue(AgentAccessRequest(request_id, agent_id))
                        top_level_request_ids.append(request_id)

                    result_artifacts: dict[str, ProvisionedAgentArtifactV1] = {}
                    pending_gateway_results = []
                    retrieval_completion_ns: dict[str, int] = {}
                    admitted_slot_by_request: dict[str, int] = {}
                    ready_slot_by_request: dict[str, int] = {}
                    queued_nested: set[int] = set()
                    origin = time.monotonic_ns() + profile.initial_lead_ms * 1_000_000
                    max_start_lateness_ms = 0.0
                    try:
                        for slot in range(profile.total_public_slots):
                            scheduled = origin + slot * profile.interval_ms * 1_000_000
                            now = time.monotonic_ns()
                            if now < scheduled:
                                time.sleep((scheduled - now) / 1e9)
                            started = time.monotonic_ns()
                            result = scheduler.execute_slot(drain=slot == profile.total_public_slots - 1)
                            completed = time.monotonic_ns()
                            max_start_lateness_ms = max(
                                max_start_lateness_ms, max(0, started - scheduled) / 1e6
                            )
                            if result is None:
                                continue
                            admitted_slot_by_request[result.request.request_id] = result.admitted_slot
                            ready_slot_by_request[result.request.request_id] = result.ready_slot
                            if result.artifact is not None:
                                result_artifacts[result.request.request_id] = result.artifact
                                retrieval_completion_ns[result.request.request_id] = completed
                                for child in result.artifact.sub_agent_ids:
                                    if child not in queued_nested:
                                        nested_id = f"{run_id}-nested-{child}"
                                        request_created_ns[nested_id] = completed
                                        scheduler.enqueue(AgentAccessRequest(nested_id, child))
                                        queued_nested.add(child)
                            else:
                                pending_gateway_results.append(result)
                    finally:
                        scheduler.close()
                    access_profile_complete_ns = time.monotonic_ns()

                    semantic_outputs: list[str] = []
                    semantic_success = True
                    task_complete_ns: int | None = None

                    def execute_semantics() -> None:
                        nonlocal semantic_success
                        by_agent = {
                            artifact.canonical_agent_id: artifact
                            for artifact in result_artifacts.values()
                        }

                        def load(agent_id: int, cache: dict[int, Any]):
                            if agent_id in cache:
                                return cache[agent_id]
                            artifact = by_agent[agent_id]
                            children = tuple(load(child, cache) for child in artifact.sub_agent_ids)
                            cache[agent_id] = AgentLoader().load(artifact, children)
                            return cache[agent_id]

                        for request_id in top_level_request_ids:
                            artifact = result_artifacts[request_id]
                            observed = load(artifact.canonical_agent_id, {}).run()
                            semantic_outputs.append(observed)
                            semantic_success &= observed == artifact.runtime_policy["expected_output"]

                    # Useful semantics are not forced to wait for an unrelated
                    # empty Gateway transcript. Provisioned and idle cases close
                    # at the framework/application boundary before the frozen
                    # Gateway tail is drained.
                    if not pending_gateway_results:
                        if top_level_request_ids:
                            execute_semantics()
                            task_complete_ns = time.monotonic_ns()
                        else:
                            task_complete_ns = access_profile_complete_ns

                    if len(gateway_queue) > 1:
                        raise RuntimeError("utility session requires at most one Internet artifact")
                    gateway_agent = gateway_queue[0] if gateway_queue else None
                    gateway_row = repository_rows[gateway_agent] if gateway_agent is not None else None
                    gateway_start_ns = time.monotonic_ns()
                    gateway_session = run_frozen_v4r8_gateway_artifact_session(
                        gateway_runner,
                        run_dir,
                        agent_id=gateway_agent,
                        artifact=gateway_row,
                    )
                    gateway_end_ns = time.monotonic_ns()
                    if pending_gateway_results:
                        if gateway_session.artifact is None:
                            raise RuntimeError("Gateway returned no queued repository artifact")
                        for pending in pending_gateway_results:
                            artifact = codec.decode(gateway_session.artifact, pending.request.agent_id)
                            result_artifacts[pending.request.request_id] = artifact
                            retrieval_completion_ns[pending.request.request_id] = gateway_end_ns
                        execute_semantics()
                        task_complete_ns = time.monotonic_ns()
                    assert task_complete_ns is not None

                    retrieval_values_ms = [
                        (retrieval_completion_ns[request_id] - request_created_ns[request_id]) / 1e6
                        for request_id in sorted(retrieval_completion_ns)
                    ]
                    profile_conformance = (
                        len(scheduler.public_slots) == 4
                        and gateway_session.public_profile["relay_cells"] == 521
                        and gateway_session.public_profile["public_transcript_complete"] is True
                        and all(
                            p.psi_messages == 4
                            and p.psi_framed_lengths == (104, 104, 697972, 1579652)
                            and p.pir_messages == 2
                            and p.pir_framed_lengths == (36388, 37180)
                            for p in scheduler.public_slots
                        )
                    )
                    gateway_result = gateway_session.result
                    rows.append(
                        {
                            "run_id": run_id,
                            "repetition": repetition,
                            "framework": framework,
                            "workload": workload,
                            "requested_agent_count": len(initial_ids),
                            "retrieved_agent_count": len(retrieval_values_ms),
                            "retrieval_latency_p50_ms": percentile(retrieval_values_ms, 0.50),
                            "retrieval_latency_p95_ms": percentile(retrieval_values_ms, 0.95),
                            "task_latency_ms": (task_complete_ns - session_start_ns) / 1e6,
                            "agent_access_profile_wall_ms": (access_profile_complete_ns - session_start_ns) / 1e6,
                            "gateway_public_wall_ms": (gateway_end_ns - gateway_start_ns) / 1e6,
                            "full_public_obligations_wall_ms": (gateway_end_ns - session_start_ns) / 1e6,
                            "semantic_success": semantic_success,
                            "profile_conformance": profile_conformance,
                            "scheduled_agent_access_slots": len(scheduler.public_slots),
                            "apsi_operations": len(scheduler.public_slots),
                            "simplepir_operations": len(scheduler.public_slots),
                            "gateway_relay_cells": gateway_session.public_profile["relay_cells"],
                            "gateway_request_bytes": gateway_session.public_profile["request_bytes"],
                            "gateway_response_bytes": gateway_session.public_profile["response_bytes"],
                            "public_transcript_complete": gateway_session.public_profile["public_transcript_complete"],
                            "admitted_real_agent_accesses": len(scheduler.results),
                            "overflow_count": int(gateway_result.get("profile_overflow_events", 0)),
                            "silent_loss_count": int(gateway_result.get("silent_committed_result_losses", 0)),
                            "dummy_heavy_agent_executions": 0,
                            "dummy_heavy_llm_executions": 0,
                            "dummy_heavy_tool_executions": 0,
                            "nested_reentry": bool(queued_nested),
                            "gateway_repository_requests": len(gateway_queue),
                            "max_agent_slot_start_lateness_ms": max_start_lateness_ms,
                            "semantic_outputs": semantic_outputs,
                            "retrieval_latencies_ms": retrieval_values_ms,
                            "admitted_slot_by_request": admitted_slot_by_request,
                            "ready_slot_by_request": ready_slot_by_request,
                        }
                    )
                    print(json.dumps({"completed": run_id, "semantic": semantic_success, "profile": profile_conformance}), flush=True)
    finally:
        sender.terminate()
        try:
            sender.wait(timeout=30)
        except subprocess.TimeoutExpired:
            sender.kill()
            sender.wait(timeout=10)

    payload = {
        "schema": "AgentTool.V15CFinalUtility/1",
        "base_v15b_commit": "2cf835cb1e63e1f6f15bfdb523f563ae8608e868",
        "profile": {
            "N": 100000,
            "R_A": 4,
            "Delta_A_ms": 350,
            "Agent_access_horizon_ms": 1425,
            "max_admitted_real_agent_accesses": 3,
            "Gateway_cells": 521,
        },
        "measured_executions": len(rows),
        "rows": rows,
    }
    (output / "v15c_final_utility_raw.json").write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()

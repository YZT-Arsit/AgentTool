from __future__ import annotations

import argparse
import hashlib
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


def sha256_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apsi-sender", type=Path, required=True)
    parser.add_argument("--apsi-receiver", type=Path, required=True)
    parser.add_argument("--apsi-db", type=Path, required=True)
    parser.add_argument("--simplepir", type=Path, required=True)
    parser.add_argument("--pir-database", type=Path, required=True)
    parser.add_argument("--aead-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=12266)
    parser.add_argument("--apsi-receiver-sha256")
    parser.add_argument("--simplepir-sha256")
    parser.add_argument("--gateway-runner", type=Path, required=True)
    parser.add_argument("--public-slots", type=int, required=True)
    parser.add_argument("--interval-ms", type=int, required=True)
    args = parser.parse_args()
    if args.public_slots < 2:
        raise ValueError("pipeline profile needs at least one admission plus one drain slot")
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    profile = AgentAccessProfile(
        f"OAE-AGENT-ACCESS-P2-RA{args.public_slots}-D{args.interval_ms}",
        args.public_slots - 1, args.interval_ms,
    ).validate()
    sender = subprocess.Popen(
        [str(args.apsi_sender), "--db", str(args.apsi_db),
         "--metrics", str(output / "apsi_sender.jsonl"), "--port", str(args.port)],
        stdout=(output / "apsi_sender_stdout.txt").open("wb"),
        stderr=(output / "apsi_sender_stderr.txt").open("wb"),
    )
    time.sleep(1)
    codec = ProvisionedAgentArtifactCodec(args.aead_key.read_bytes(), STORE_EPOCH)
    functional = {value.canonical_agent_id: value for value in functional_artifacts()}
    repository_rows = {
        agent_id: codec.encode(artifact) for agent_id, artifact in functional.items()
        if agent_id > SCALE_RECORDS
    }
    session_specs = [
        ("ZERO_REQUEST", []),
        ("DEPLOYED_ONLY", [101]),
        ("UNPROVISIONED_ONLY", [1_000_101]),
        ("REPEATED_SAME_AGENT", [101, 101, 101]),
        ("ALTERNATING_AGENTS", [101, 1_000_101, 101]),
        ("NESTED_AGENT", [102]),
        ("MIXED_OPENAI", [101, 1_000_101]),
        ("MIXED_MICROSOFT", [201, 1_000_201]),
    ]
    sessions: list[dict[str, Any]] = []
    try:
        with RealLabeledAPSIClient(
            args.apsi_receiver, f"tcp://127.0.0.1:{args.port}",
            expected_sha256=args.apsi_receiver_sha256,
        ) as psi, PersistentSimplePIRArtifactClient(
            args.simplepir, args.pir_database, SCALE_RECORDS + 1,
            output / "simplepir", expected_sha256=args.simplepir_sha256,
        ) as pir:
            for session_index, (name, initial_ids) in enumerate(session_specs):
                gateway_queue: list[int] = []
                scheduler = PipelinedAgentAccessScheduler(
                    profile, psi, pir, codec, dummy_row=DUMMY_PIR_ROW,
                    gateway_queue=gateway_queue.append,
                )
                top_level_request_ids: list[str] = []
                for index, agent_id in enumerate(initial_ids):
                    request_id = f"{name}-initial-{index}"
                    scheduler.enqueue(AgentAccessRequest(request_id, agent_id))
                    top_level_request_ids.append(request_id)
                result_artifacts: dict[str, ProvisionedAgentArtifactV1] = {}
                pending_gateway_results = []
                origin = time.monotonic_ns() + profile.initial_lead_ms * 1_000_000
                lateness: list[float] = []
                queued_nested: set[int] = set()
                try:
                    for slot in range(profile.total_public_slots):
                        scheduled = origin + slot * profile.interval_ms * 1_000_000
                        now = time.monotonic_ns()
                        if now < scheduled: time.sleep((scheduled - now) / 1e9)
                        started = time.monotonic_ns()
                        result = scheduler.execute_slot(
                            drain=slot == profile.total_public_slots - 1
                        )
                        lateness.append(max(0, started - scheduled) / 1e6)
                        if result is not None:
                            if result.artifact is not None:
                                artifact = result.artifact
                            else:
                                pending_gateway_results.append(result)
                                artifact = None
                            if artifact is not None:
                                result_artifacts[result.request.request_id] = artifact
                            if artifact is None:
                                continue
                            for child in artifact.sub_agent_ids:
                                if child not in queued_nested:
                                    scheduler.enqueue(AgentAccessRequest(f"{name}-nested-{child}", child))
                                    queued_nested.add(child)
                finally:
                    scheduler.close()

                if len(gateway_queue) > 1:
                    raise RuntimeError("test session requires more than one repository artifact")
                gateway_agent = gateway_queue[0] if gateway_queue else None
                gateway_row = repository_rows[gateway_agent] if gateway_agent is not None else None
                gateway_session = run_frozen_v4r8_gateway_artifact_session(
                    args.gateway_runner,
                    output / "gateway_sessions" / f"{session_index:02d}_{name}",
                    agent_id=gateway_agent,
                    artifact=gateway_row,
                )
                if pending_gateway_results:
                    if gateway_session.artifact is None:
                        raise RuntimeError("Gateway returned no queued repository artifact")
                    for result in pending_gateway_results:
                        artifact = codec.decode(gateway_session.artifact, result.request.agent_id)
                        result_artifacts[result.request.request_id] = artifact

                by_agent = {artifact.canonical_agent_id: artifact for artifact in result_artifacts.values()}
                def load(agent_id: int, loaded_cache: dict[int, Any]):
                    if agent_id in loaded_cache: return loaded_cache[agent_id]
                    artifact = by_agent[agent_id]
                    children = tuple(load(child, loaded_cache) for child in artifact.sub_agent_ids)
                    loaded_cache[agent_id] = AgentLoader().load(artifact, children)
                    return loaded_cache[agent_id]
                semantic_outputs = []
                semantic_ok = True
                for request_id in top_level_request_ids:
                    artifact = result_artifacts[request_id]
                    # Framework fixtures use stateful one-shot scripted models;
                    # each logical execution reconstructs a fresh native Agent
                    # from the same authenticated artifact.
                    output_value = load(artifact.canonical_agent_id, {}).run()
                    semantic_outputs.append(output_value)
                    semantic_ok &= output_value == artifact.runtime_policy["expected_output"]
                public = [value.canonical() for value in scheduler.public_slots]
                sessions.append({
                    "session": name, "requested_agents_private": initial_ids,
                    "scheduled_public_slots": len(public), "apsi_operations": len(public),
                    "simplepir_operations": len(public), "pipeline_results": len(scheduler.results),
                    "gateway_repository_requests_private": list(gateway_queue),
                    "semantic_outputs": semantic_outputs, "semantic_success": semantic_ok,
                    "nested_reentry": bool(queued_nested), "nested_agent_ids_private": sorted(queued_nested),
                    "max_start_lateness_ms": max(lateness),
                    "public_projection": public, "public_projection_sha256": sha256_json(public),
                    "gateway_public_projection": gateway_session.public_profile,
                    "real_apsi": True, "real_simplepir": True,
                    "gateway_profile_changed": False,
                })
    finally:
        sender.terminate()
        try: sender.wait(timeout=30)
        except subprocess.TimeoutExpired:
            sender.kill(); sender.wait(timeout=10)

    projections = [row["public_projection"] for row in sessions]
    gateway_projections = [row["gateway_public_projection"] for row in sessions]
    structurally_equal = (
        all(value == projections[0] for value in projections[1:])
        and all(value == gateway_projections[0] for value in gateway_projections[1:])
    )
    full = {
        "schema": "AgentTool.V15BFullSessionResults/1",
        "profile": {
            "profile_id": profile.profile_id, "R_A_public_slots": profile.total_public_slots,
            "Delta_A_ms": profile.interval_ms, "initial_lead_ms": profile.initial_lead_ms,
            "Agent_access_horizon_ms": profile.public_horizon_ms,
            "maximum_admitted_agent_requests": profile.real_admission_slots,
            "guaranteed_serial_causal_depth": profile.guaranteed_serial_causal_depth,
            "bootstrap_slots": 1, "drain_slots": 1,
        },
        "sessions": sessions, "all_semantic_success": all(row["semantic_success"] for row in sessions),
        "full_session_schedule_pass": all(
            row["scheduled_public_slots"] == profile.total_public_slots
            and row["apsi_operations"] == profile.total_public_slots
            and row["simplepir_operations"] == profile.total_public_slots
            for row in sessions
        ),
        "structural_equivalence": structurally_equal,
    }
    (output / "V15B_FULL_SESSION_RESULTS.json").write_text(json.dumps(full, indent=2) + "\n")
    structural = {
        "schema": "AgentTool.V15BStructuralEquivalence/1",
        "profile_id": profile.profile_id,
        "sessions": [row["session"] for row in sessions],
        "projection_fields": [
            "slot", "profile_id", "psi_public_endpoint", "psi_messages", "psi_framed_lengths",
            "pir_public_endpoint", "pir_messages", "pir_framed_lengths", "gateway_public_endpoint",
            "gateway_frame_count", "gateway_directions", "gateway_frame_lengths",
        ],
        "excluded": [
            "realized_wall_clock_timestamps", "AgentID", "PIR row", "hit/miss",
            "queue occupancy", "artifact", "source class",
        ],
        "projection_sha256": {row["session"]: row["public_projection_sha256"] for row in sessions},
        "gateway_projection_sha256": {
            row["session"]: sha256_json(row["gateway_public_projection"]) for row in sessions
        },
        "exact_equality": structurally_equal, "timing_indistinguishability_claimed": False,
    }
    (output / "V15B_STRUCTURAL_EQUIVALENCE.json").write_text(json.dumps(structural, indent=2) + "\n")
    if not (full["all_semantic_success"] and full["full_session_schedule_pass"] and structurally_equal):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

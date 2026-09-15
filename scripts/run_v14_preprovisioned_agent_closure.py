from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import time
from pathlib import Path

from v14_provisioned_agents.artifact import PIR_RECORD_BYTES, ProvisionedAgentArtifactCodec
from v14_provisioned_agents.fixtures import (
    DUMMY_PIR_ROW,
    SCALE_RECORDS,
    STORE_EPOCH,
    functional_artifacts,
    make_artifact,
    scale_row_for_agent,
)
from v14_provisioned_agents.loader import AgentLoader
from v14_provisioned_agents.models import AgentFramework, PIRRowHandle
from v14_provisioned_agents.psi import (
    APSI_COMMIT,
    APSI_REPOSITORY,
    APSI_VERSION,
    RealLabeledAPSIClient,
    write_sender_input,
)
from v14_provisioned_agents.resolution import PaperAlignedAgentResolver
from v14_provisioned_agents.simplepir import PersistentSimplePIRArtifactClient, SIMPLEPIR_COMMIT


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def public_gateway_profile() -> dict[str, object]:
    return {
        "profile": "V12-TIMING-INDIST-V4R8-H50-H4500-P10-B200-PIR60",
        "common_endpoint": "TRUSTED_GATEWAY",
        "request_cells": 521,
        "response_cells": 521,
        "request_bytes": 1079,
        "response_bytes": 800,
        "agent_specific_destination": False,
    }


class FixedProfileInternetArtifactGateway:
    """Development repository adapter behind the unchanged public Gateway profile."""

    def __init__(self, rows: dict[int, bytes]):
        self.rows = rows
        self.requests: list[int] = []

    def retrieve_artifact(self, agent_id: int) -> bytes:
        self.requests.append(agent_id)
        try:
            return self.rows[agent_id]
        except KeyError as exc:
            raise RuntimeError("Internet Agent Repository miss") from exc

    def public_profile(self) -> dict[str, object]:
        return public_gateway_profile()


def prepare(work: Path) -> dict[str, object]:
    work.mkdir(parents=True, exist_ok=False)
    key_path = work / "artifact_aead_key.private"
    key_path.write_bytes(os.urandom(32))
    if os.name != "nt":
        key_path.chmod(0o600)
    codec = ProvisionedAgentArtifactCodec(key_path.read_bytes(), STORE_EPOCH)
    functional = {a.canonical_agent_id: a for a in functional_artifacts()}
    measured = []
    for artifact in functional.values():
        size = codec.plaintext_size(artifact)
        measured.append(
            {
                "agent_id": artifact.canonical_agent_id,
                "framework": artifact.framework.value,
                "name": artifact.name,
                "plaintext_serialized_bytes": size,
                "protected_serialized_bytes": PIR_RECORD_BYTES,
                "payload_capacity_bytes": codec.payload_capacity,
                "headroom_bytes": codec.payload_capacity - size,
            }
        )
    with (work / "artifact_size_audit.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(measured[0]))
        writer.writeheader(); writer.writerows(measured)
    sizes = [row["plaintext_serialized_bytes"] for row in measured]

    db = work / "provisioned_agent_store_100k_plus_dummy.bin"
    with db.open("w+b") as stream:
        stream.truncate((SCALE_RECORDS + 1) * PIR_RECORD_BYTES)
        for agent_id in range(1, SCALE_RECORDS + 1):
            artifact = functional.get(agent_id)
            if artifact is None:
                framework = (
                    AgentFramework.OPENAI_AGENTS_SDK
                    if agent_id % 2 else AgentFramework.MICROSOFT_AGENT_FRAMEWORK
                )
                artifact = make_artifact(
                    agent_id, framework, role=f"scale-template-{agent_id % 16:02d}",
                    synthetic_scale=True,
                )
            row_index = scale_row_for_agent(agent_id)
            stream.seek(row_index * PIR_RECORD_BYTES)
            stream.write(codec.encode(artifact))
        stream.seek(DUMMY_PIR_ROW * PIR_RECORD_BYTES)
        stream.write(os.urandom(PIR_RECORD_BYTES))

    # Every one of the 100,000 scale rows must authenticate, decode, and bind to its ID.
    with db.open("rb") as stream:
        for agent_id in range(1, SCALE_RECORDS + 1):
            stream.seek(scale_row_for_agent(agent_id) * PIR_RECORD_BYTES)
            codec.decode(stream.read(PIR_RECORD_BYTES), agent_id)

    sender_input = work / "apsi_sender_input_100k.bin"
    sender_input_info = write_sender_input(
        (
            (agent_id, PIRRowHandle(scale_row_for_agent(agent_id), STORE_EPOCH))
            for agent_id in range(1, SCALE_RECORDS + 1)
        ),
        sender_input,
    )
    result = {
        "scale_records": SCALE_RECORDS,
        "dummy_rows": 1,
        "simplepir_total_rows": SCALE_RECORDS + 1,
        "pir_record_bytes": PIR_RECORD_BYTES,
        "database_bytes": db.stat().st_size,
        "database_sha256": sha256(db),
        "schema_valid_rows_decoded": SCALE_RECORDS,
        "real_world_unique_agents": False,
        "functional_agent_artifacts": len(functional),
        "functional_size_bytes": {
            "min": min(sizes),
            "p50": percentile(sizes, 0.5),
            "p95": percentile(sizes, 0.95),
            "max": max(sizes),
            "minimum_headroom": codec.payload_capacity - max(sizes),
        },
        "row_mapping": "j=((AgentID-1)*65537+17) mod 100000",
        "agent_id_equals_row": False,
        "apsi_sender_input": sender_input_info,
        "private_key_path": str(key_path),
    }
    dump(work / "dataset_preparation.json", result)
    return result


def build_sender(work: Path, args: argparse.Namespace) -> dict[str, object]:
    command = [
        str(args.apsi_builder), str(args.apsi_params),
        str(work / "apsi_sender_input_100k.bin"), str(work / "apsi_sender_db.bin"),
        str(work / "apsi_sender_build_stats.json"),
    ]
    subprocess.run(command, check=True)
    return json.loads((work / "apsi_sender_build_stats.json").read_text())


def flatten_resolutions(value):
    yield value
    for child in value.nested_resolutions:
        yield from flatten_resolutions(child)


def execute(work: Path, evidence: Path, args: argparse.Namespace) -> None:
    evidence.mkdir(parents=True, exist_ok=False)
    prep = json.loads((work / "dataset_preparation.json").read_text())
    codec = ProvisionedAgentArtifactCodec(
        (work / "artifact_aead_key.private").read_bytes(), STORE_EPOCH
    )
    sender = subprocess.Popen(
        [str(args.apsi_sender), "--db", str(work / "apsi_sender_db.bin"),
         "--metrics", str(work / "apsi_sender_service.jsonl"), "--port", str(args.port)],
        stdout=(work / "apsi_sender_stdout.txt").open("wb"),
        stderr=(work / "apsi_sender_stderr.txt").open("wb"),
    )
    time.sleep(1)
    psi_rows: list[dict[str, object]] = []
    pir_rows: list[dict[str, object]] = []
    loader_rows: list[dict[str, object]] = []
    e2e_rows: list[dict[str, object]] = []
    try:
        with RealLabeledAPSIClient(
            args.apsi_receiver, f"tcp://127.0.0.1:{args.port}"
        ) as psi:
            # Fresh real queries: ten each for hit, miss, and idle.
            for case, agent_id in (
                ("PROVISIONED", 101), ("UNPROVISIONED", 1_000_101), ("IDLE", None)
            ):
                for repetition in range(1, 11):
                    result = psi.query(agent_id)
                    psi_rows.append({
                        "case": case, "repetition": repetition,
                        "found": result.row_handle is not None,
                        "oprf_request_bytes": result.wire.oprf_request_bytes,
                        "oprf_response_bytes": result.wire.oprf_response_bytes,
                        "query_request_bytes": result.wire.query_request_bytes,
                        "query_response_bytes": result.wire.query_response_bytes,
                        "request_messages": 2, "response_messages": 2, "protocol_rounds": 2,
                        "oprf_ms": result.wire.oprf_ns / 1e6,
                        "query_construction_ms": result.wire.query_construction_ns / 1e6,
                        "query_roundtrip_ms": result.wire.query_roundtrip_ns / 1e6,
                        "result_processing_ms": result.wire.result_processing_ns / 1e6,
                    })

            repository_rows = {
                artifact.canonical_agent_id: codec.encode(artifact)
                for artifact in functional_artifacts()
                if artifact.canonical_agent_id > SCALE_RECORDS
            }
            gateway = FixedProfileInternetArtifactGateway(repository_rows)
            with PersistentSimplePIRArtifactClient(
                args.simplepir, work / "provisioned_agent_store_100k_plus_dummy.bin",
                SCALE_RECORDS + 1, work / "simplepir_run"
            ) as pir:
                resolver = PaperAlignedAgentResolver(
                    psi, pir, codec, AgentLoader(), gateway, dummy_row=DUMMY_PIR_ROW
                )
                cases = []
                for framework, base in (
                    (AgentFramework.OPENAI_AGENTS_SDK, 101),
                    (AgentFramework.MICROSOFT_AGENT_FRAMEWORK, 201),
                ):
                    cases.extend([
                        (framework, "PROVISIONED_ORDINARY", base),
                        (framework, "UNPROVISIONED_ORDINARY", 1_000_000 + base),
                        (framework, "PROVISIONED_NESTED", base + 1),
                        (framework, "UNPROVISIONED_NESTED", 1_000_001 + base),
                        (framework, "IDLE", None),
                    ])
                for framework, case, agent_id in cases:
                    started = time.perf_counter_ns()
                    resolved = resolver.resolve(agent_id)
                    resolution_ms = (time.perf_counter_ns() - started) / 1e6
                    if resolved.loaded is None:
                        output = None; semantic_ok = case == "IDLE"; executed = False
                    else:
                        output = resolved.loaded.run()
                        semantic_ok = output == resolved.artifact.runtime_policy["expected_output"]
                        executed = True
                        loader_rows.append({**resolved.loaded.evidence(), "case": case, "output": output})
                    all_resolutions = list(flatten_resolutions(resolved))
                    for index, item in enumerate(all_resolutions):
                        pir_rows.append({
                            "framework": framework.value, "case": case,
                            "resolution_ordinal": index + 1,
                            "kind": item.kind.value,
                            "query_bytes": item.pir.query_bytes,
                            "answer_bytes": item.pir.answer_bytes,
                            "correct": item.pir.correct,
                            "queried_dummy": item.kind.value != "PROVISIONED",
                        })
                    e2e_rows.append({
                        "framework": framework.value, "case": case,
                        "requested_agent_id": agent_id, "resolution_kind": resolved.kind.value,
                        "resolution_ms": resolution_ms, "semantic_output": output,
                        "semantic_success": semantic_ok, "agent_executed": executed,
                        "agent_access_slots": len(all_resolutions),
                        "nested_reentry": len(resolved.nested_resolutions) > 0,
                        "real_apsi": True, "real_simplepir": True,
                        "gateway_repository_retrieval": resolved.gateway_repository_retrieval,
                        "remote_agent_service_executions": resolver.remote_provisioned_agent_executions,
                        "agent_specific_gateway_destinations": resolver.agent_specific_gateway_destinations,
                    })
    finally:
        sender.terminate()
        try: sender.wait(timeout=10)
        except subprocess.TimeoutExpired:
            sender.kill(); sender.wait(timeout=10)

    for name, rows in (
        ("V14_REAL_PSI_RESULTS.csv", psi_rows),
        ("V14_REAL_PIR_RESULTS.csv", pir_rows),
    ):
        with (evidence / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    dump(evidence / "V14_AGENT_LOADER_RESULTS.json", {
        "executions": loader_rows, "e2e": e2e_rows,
        "openai_pass": all(r["semantic_success"] for r in e2e_rows if r["framework"] == AgentFramework.OPENAI_AGENTS_SDK.value),
        "microsoft_pass": all(r["semantic_success"] for r in e2e_rows if r["framework"] == AgentFramework.MICROSOFT_AGENT_FRAMEWORK.value),
    })
    wire_fields = [
        "oprf_request_bytes", "oprf_response_bytes", "query_request_bytes",
        "query_response_bytes", "request_messages", "response_messages", "protocol_rounds",
    ]
    patterns = {
        case: sorted({tuple(row[k] for k in wire_fields) for row in psi_rows if row["case"] == case})
        for case in ("PROVISIONED", "UNPROVISIONED", "IDLE")
    }
    pir_patterns = sorted({(r["query_bytes"], r["answer_bytes"]) for r in pir_rows})
    equality = len(set(json.dumps(v) for v in patterns.values())) == 1 and len(pir_patterns) == 1
    dump(evidence / "V14_PUBLIC_STRUCTURE_EQUIVALENCE.json", {
        "projection_fields": wire_fields + ["pir_query_bytes", "pir_answer_bytes", "gateway_public_profile"],
        "psi_patterns": patterns, "pir_patterns": pir_patterns,
        "gateway_public_profile": public_gateway_profile(),
        "provisioned_unprovisioned_idle_equal": equality,
        "timing_excluded": True,
    })
    build_stats = json.loads((work / "apsi_sender_build_stats.json").read_text())
    provenance = {
        "repository": APSI_REPOSITORY, "commit": APSI_COMMIT, "version": APSI_VERSION,
        "source_modified": False, "sender_records": SCALE_RECORDS,
        "params_sha256": sha256(args.apsi_params),
        "receiver_binary_sha256": sha256(args.apsi_receiver),
        "sender_binary_sha256": sha256(args.apsi_sender),
        "builder_binary_sha256": sha256(args.apsi_builder),
        "simplepir_commit": SIMPLEPIR_COMMIT,
        "simplepir_binary_sha256": sha256(args.simplepir),
        "sender_db_preprocessing": build_stats,
    }
    dump(evidence / "V14_REAL_PSI_PROVENANCE.json", provenance)
    shutil.copy2(work / "artifact_size_audit.csv", evidence / "V14_AGENT_ARTIFACT_SIZE_AUDIT.csv")
    dump(evidence / "V14_E2E_RESULTS.json", e2e_rows)
    dump(evidence / "V14_DATASET_RESULTS.json", prep)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--apsi-builder", type=Path)
    parser.add_argument("--apsi-sender", type=Path)
    parser.add_argument("--apsi-receiver", type=Path)
    parser.add_argument("--apsi-params", type=Path)
    parser.add_argument("--simplepir", type=Path)
    parser.add_argument("--port", type=int, default=14141)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.work)
    if args.execute:
        required = (args.evidence, args.apsi_builder, args.apsi_sender, args.apsi_receiver, args.apsi_params, args.simplepir)
        if any(value is None for value in required):
            parser.error("--execute requires all evidence/backend paths")
        build_sender(args.work, args)
        execute(args.work, args.evidence, args)


if __name__ == "__main__":
    main()

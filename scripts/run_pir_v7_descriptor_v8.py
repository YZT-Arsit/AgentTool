from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from action_privacy_v8.descriptor import AGENT_DESCRIPTOR_V7_BYTES, AgentDescriptorV7Codec
from action_privacy_v8.models import (
    AgentDescriptorV7,
    AgentServiceRouteDescriptor,
    EffectSemantics,
    PlacementClass,
)
from action_privacy_v8.pir_boundary import audit_server_log
from cryptographic_closure.pir_backend import PIRRequest, read_raw_queries, run_simplepir


OUT = ROOT / "results_v8" / "pir_v7_descriptor"
CSV = ROOT / "PIR_V7_DESCRIPTOR_RESULTS_V8.csv"
EPOCH = 20260828


def descriptor(index: int) -> AgentDescriptorV7:
    placement = (
        PlacementClass.TRUSTED_MODULE_LOCAL
        if index % 11 == 0
        else PlacementClass.CLOUD_LOCAL
        if index % 5 == 0
        else PlacementClass.EXTERNAL
    )
    semantics = tuple(EffectSemantics)[index % len(EffectSemantics)]
    return AgentDescriptorV7(
        agent_id=index,
        capability_ids=(f"agent.capability.{index}",),
        publisher_key_id=f"publisher-{index % 17}",
        agent_version=1 + index % 7,
        placement=placement,
        agent_service=AgentServiceRouteDescriptor(
            route_handle=f"agent-service-route-{index}",
            effect_semantics=semantics,
            policy_id=f"agent-service-policy-{index % 23}",
            placement=placement,
        ),
        allowed_tool_capabilities=(f"tool.class.{index % 31}",),
        trust_class="SIGNED_EXTERNAL" if placement is PlacementClass.EXTERNAL else "ENTERPRISE",
        catalog_epoch=EPOCH,
    )


def build_registry(path: Path, count: int, codec: AgentDescriptorV7Codec) -> tuple[str, float]:
    started = time.perf_counter()
    digest = hashlib.sha256()
    with path.open("xb") as handle:
        for index in range(count):
            row = codec.encode(descriptor(index))
            handle.write(row)
            digest.update(row)
    if path.stat().st_size != count * AGENT_DESCRIPTOR_V7_BYTES:
        raise AssertionError("V7 descriptor registry physical size mismatch")
    return digest.hexdigest(), (time.perf_counter() - started) * 1000.0


def main() -> None:
    if CSV.exists():
        raise FileExistsError(f"refusing to overwrite {CSV}")
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for count in (1_000, 10_000, 100_000):
        run_dir = OUT / f"n_{count}"
        if run_dir.exists() and any(run_dir.iterdir()):
            raise FileExistsError(f"refusing to overwrite {run_dir}")
        run_dir.mkdir(parents=True)
        codec = AgentDescriptorV7Codec(os.urandom(32), EPOCH)
        registry = run_dir / "encrypted_agent_descriptor_v7_rows.bin"
        registry_digest, encryption_ms = build_registry(registry, count, codec)
        indices = (0, count // 2, count // 2, count - 2, count - 1)
        requests = [
            PIRRequest(f"v8-v7-descriptor-{count}", ordinal, index, "PRIVATE_SELECTION")
            for ordinal, index in enumerate(indices)
        ]
        artifacts = run_simplepir(ROOT, registry, count, requests, run_dir / "simplepir")
        recovered = [
            codec.decode(row, expected_agent_id=index)
            for row, index in zip(artifacts.recovered, indices, strict=True)
        ]
        correct = all(value == descriptor(index) for value, index in zip(recovered, indices, strict=True))
        raw_queries = read_raw_queries(artifacts.raw_query_path)
        repeated_fresh = hashlib.sha256(raw_queries[1]).digest() != hashlib.sha256(raw_queries[2]).digest()
        server_log_path = run_dir / "simplepir" / "server_visible_trace.jsonl"
        server_text = server_log_path.read_text(encoding="utf-8")
        audit_server_log(server_text)
        private_tokens = (
            "agent.capability.", "agent-service-route-", "agent-service-policy-",
            "tool.class.", "publisher-", "private_selection",
        )
        server_private_field = any(token in server_text.lower() for token in private_tokens)
        if server_private_field:
            raise AssertionError("private descriptor field appeared in server trace")
        metrics = artifacts.metrics
        row = {
            "freeze_id": "V8_V7_DESCRIPTOR_CANONICAL_20260828",
            "platform": "Windows-local-Go-CGO",
            "descriptor_schema": "AgentDescriptorV7/7",
            "catalog_epoch": EPOCH,
            "logical_records": count,
            "logical_bytes": count * AGENT_DESCRIPTOR_V7_BYTES,
            "physical_record_capacity": metrics["physical_record_capacity"],
            "physical_bytes": metrics["physical_bytes"],
            "padding_bytes": metrics["padding_bytes"],
            "descriptor_bytes": AGENT_DESCRIPTOR_V7_BYTES,
            "registry_sha256": registry_digest,
            "descriptor_encryption_build_ms": round(encryption_ms, 3),
            "database_construction_ms": metrics["database_construction_ms"],
            "full_preprocessing_setup_ms": metrics["full_preprocessing_setup_ms"],
            "query_generation_ms": metrics["mean_query_generation_ms"],
            "server_answer_ms": metrics["mean_server_answer_ms"],
            "recovery_ms": metrics["mean_client_recovery_ms"],
            "upload_bytes": metrics["online_upload_bytes"],
            "download_bytes": metrics["online_download_bytes"],
            "client_state_bytes": metrics["persistent_client_state_bytes"],
            "hint_bytes": metrics["hint_bytes"],
            "peak_memory_bytes": metrics["peak_allocated_bytes"],
            "queries": len(indices),
            "correct_queries": sum(item is not None for item in recovered) if correct else 0,
            "descriptor_authentication": correct,
            "expected_agent_id_match": correct,
            "fresh_repeated_queries": repeated_fresh,
            "server_trace_private_field": server_private_field,
            "backend": metrics["backend"],
            "simplepir_commit": metrics["commit"],
            "result_path": str(run_dir.relative_to(ROOT)).replace("\\", "/"),
        }
        rows.append(row)
        (run_dir / "trusted_private_verification.json").write_text(
            json.dumps(
                {
                    "indices": indices,
                    "descriptor_authentication": correct,
                    "expected_agent_id_match": correct,
                    "fresh_repeated_queries": repeated_fresh,
                    "server_trace_private_field": server_private_field,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(json.dumps(row, indent=2))
    with CSV.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

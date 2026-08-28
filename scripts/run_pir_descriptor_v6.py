from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from pathlib import Path

from action_privacy_v6.descriptor import (DESCRIPTOR_BYTES, AgentDescriptorV6,
                                          DescriptorCodec, PlacementClass)
from cryptographic_closure.pir_backend import (PIRRequest, read_raw_queries,
                                               run_simplepir)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_v6" / "pir_descriptor"
CSV = ROOT / "PIR_DESCRIPTOR_RESULTS_V6.csv"


def descriptor(index: int, epoch: int) -> AgentDescriptorV6:
    external = index % 5 == 0
    return AgentDescriptorV6(
        index, (f"capability-{index}",), f"publisher-{index % 17}", 1 + index % 7,
        PlacementClass.EXTERNAL if external else PlacementClass.CLOUD_LOCAL,
        f"route-{index}", "framework-native-service-v6", (f"tool-class-{index % 31}",),
        "SIGNED_EXTERNAL" if external else "ENTERPRISE", epoch,
    )


def build(path: Path, count: int, codec: DescriptorCodec, epoch: int) -> tuple[str, float]:
    started = time.perf_counter()
    digest = hashlib.sha256()
    with path.open("xb") as handle:
        for index in range(count):
            row = codec.encode(descriptor(index, epoch))
            handle.write(row); digest.update(row)
    if path.stat().st_size != count * DESCRIPTOR_BYTES:
        raise AssertionError("encrypted descriptor registry was not physically instantiated")
    return digest.hexdigest(), (time.perf_counter() - started) * 1000


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
        key, epoch = os.urandom(32), 20260828
        codec = DescriptorCodec(key, epoch)
        registry = run_dir / "encrypted_agent_descriptors.bin"
        registry_digest, encryption_ms = build(registry, count, codec, epoch)
        indices = (0, count // 2, count // 2, count - 2, count - 1)
        requests = [PIRRequest(f"v6-{count}", ordinal, index,
                               "DUMMY" if index == count - 1 else "REAL")
                    for ordinal, index in enumerate(indices)]
        artifacts = run_simplepir(ROOT, registry, count, requests, run_dir / "simplepir")
        recovered = [codec.decode(row, index) for row, index in zip(artifacts.recovered, indices, strict=True)]
        correct = all(item.agent_id == index for item, index in zip(recovered, indices, strict=True))
        raw_queries = read_raw_queries(artifacts.raw_query_path)
        repeated_fresh = hashlib.sha256(raw_queries[1]).digest() != hashlib.sha256(raw_queries[2]).digest()
        metrics = artifacts.metrics
        server_text = (run_dir / "simplepir" / "server_visible_trace.jsonl").read_text(encoding="utf-8").lower()
        forbidden = any(value in server_text for value in ("private_index", "agent_name", "logical_agent", "route-"))
        row = {
            "logical_records": count, "logical_bytes": count * DESCRIPTOR_BYTES,
            "physical_record_capacity": metrics["physical_record_capacity"],
            "physical_bytes": metrics["physical_bytes"], "padding_bytes": metrics["padding_bytes"],
            "descriptor_bytes": DESCRIPTOR_BYTES, "encrypted_rows": True,
            "registry_sha256": registry_digest, "record_encryption_ms": round(encryption_ms, 3),
            "database_construction_ms": metrics["database_construction_ms"],
            "full_preprocessing_setup_ms": metrics["full_preprocessing_setup_ms"],
            "hint_bytes": metrics["hint_bytes"], "client_state_bytes": metrics["persistent_client_state_bytes"],
            "mean_query_generation_ms": metrics["mean_query_generation_ms"],
            "mean_server_answer_ms": metrics["mean_server_answer_ms"],
            "mean_recovery_ms": metrics["mean_client_recovery_ms"],
            "upload_bytes": metrics["online_upload_bytes"], "download_bytes": metrics["online_download_bytes"],
            "peak_allocated_bytes": metrics["peak_allocated_bytes"],
            "queries": len(indices), "correct": correct, "fresh_repeated_queries": repeated_fresh,
            "server_trace_private_field": forbidden, "unified_internal_external_rows": True,
            "backend": metrics["backend"], "commit": metrics["commit"],
        }
        rows.append(row)
        (run_dir / "v6_private_verification.json").write_text(json.dumps({
            "indices": indices, "correct": correct, "fresh_repeated_queries": repeated_fresh,
            "server_trace_private_field": forbidden,
        }, indent=2), encoding="utf-8")
        print(json.dumps(row, indent=2))
    with CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    main()

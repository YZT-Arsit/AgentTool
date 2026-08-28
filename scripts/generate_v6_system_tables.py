from __future__ import annotations

import csv
import json
import statistics
import time
from pathlib import Path

from action_privacy_v6.descriptor import AgentDescriptorV6, DescriptorCodec, PlacementClass
from action_privacy_v6.trusted_module import LocalTrustedBackend


ROOT = Path(__file__).resolve().parents[1]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def main() -> None:
    pir = {int(row["logical_records"]): row for row in csv.DictReader((ROOT / "PIR_DESCRIPTOR_RESULTS_V6.csv").open())}
    p10, p100 = pir[10_000], pir[100_000]
    def latency(row):
        return sum(float(row[key]) for key in ("mean_query_generation_ms", "mean_server_answer_ms", "mean_recovery_ms"))
    def bandwidth(row): return int(row["upload_bytes"]) + int(row["download_bytes"])

    pareto = []
    for hit in (0.0, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0):
        pareto.append({
            "internal_hit_probability": hit, "design": "UNIFIED_PRIVATE_REGISTRY",
            "mean_pir_latency_ms_component_model": latency(p100), "mean_pir_bytes_component_model": bandwidth(p100),
            "pir_queries_per_resolution": 1, "route_class_leakage": "NONE",
            "evidence": "weighted model from measured 100K SimplePIR component",
        })
        pareto.append({
            "internal_hit_probability": hit, "design": "HIERARCHICAL_PRIVATE_RESOLUTION",
            "mean_pir_latency_ms_component_model": hit * latency(p10) + (1-hit) * latency(p100),
            "mean_pir_bytes_component_model": round(hit * bandwidth(p10) + (1-hit) * bandwidth(p100)),
            "pir_queries_per_resolution": 1, "route_class_leakage": "INTERNAL_EXTERNAL_ROUTE_CLASS",
            "evidence": "weighted model from measured 10K internal and 100K external SimplePIR components",
        })
    write_csv(ROOT / "RESOLUTION_PARETO_V6.csv", pareto)

    cache = []
    for hit in (0.0, 0.25, 0.5, 0.75, 0.9, 1.0):
        cache.extend((
            {"profile": "STRICT", "cache_hit_probability": hit, "real_queries": 1-hit,
             "dummy_queries": hit, "total_public_queries": 1, "expected_pir_latency_ms": latency(p100),
             "expected_bytes": bandwidth(p100), "cache_hit_leakage": "NONE_BY_SCHEDULE"},
            {"profile": "ENTERPRISE_EFFICIENT", "cache_hit_probability": hit, "real_queries": 1-hit,
             "dummy_queries": 0, "total_public_queries": 1-hit,
             "expected_pir_latency_ms": (1-hit) * latency(p100),
             "expected_bytes": round((1-hit) * bandwidth(p100)), "cache_hit_leakage": "DECLARED"},
        ))
    write_csv(ROOT / "DESCRIPTOR_CACHE_RESULTS_V6.csv", cache)

    index = {f"capability-{i}": i for i in range(100_000)}
    trusted = LocalTrustedBackend(index, bytes(range(32)), bytes(reversed(range(32))), 1)
    mapping_samples = []
    for i in range(10_000):
        started = time.perf_counter_ns(); trusted.capability_to_agent_id(f"capability-{i % 100000}")
        mapping_samples.append(time.perf_counter_ns() - started)
    capability_index_bytes = trusted.capability_index_bytes
    direct_samples = []
    for _ in range(10_000):
        started = time.perf_counter_ns(); _ = b"synthetic"[::-1]
        direct_samples.append(time.perf_counter_ns() - started)
    performance = [
        {"baseline": "B0_DIRECT_NATIVE", "status": "MEASURED_LOCAL_MICROBENCH",
         "selection_ms": statistics.mean(mapping_samples)/1e6, "pir_ms": 0,
         "gateway_ms": 0, "provider_ms": "EXCLUDED", "cover_wait_ms": 0,
         "total_privacy_overhead_ms": statistics.mean(direct_samples)/1e6,
         "bytes": 0, "route_leakage": "CONCRETE_DESTINATION", "dummy_heavy_ops": 0},
        {"baseline": "B1_DIRECT_TLS", "status": "NOT_AVAILABLE_OFFLINE_NOT_IMPLEMENTED",
         "selection_ms": "", "pir_ms": "", "gateway_ms": "", "provider_ms": "EXCLUDED",
         "cover_wait_ms": "", "total_privacy_overhead_ms": "", "bytes": "",
         "route_leakage": "DESTINATION_COUNT_ORDER_TIMING", "dummy_heavy_ops": 0},
        {"baseline": "B2_PIR_ONLY", "status": "MEASURED_COMPONENTS",
         "selection_ms": statistics.mean(mapping_samples)/1e6, "pir_ms": latency(p100),
         "gateway_ms": 0, "provider_ms": "EXCLUDED", "cover_wait_ms": 0,
         "total_privacy_overhead_ms": latency(p100), "bytes": bandwidth(p100),
         "route_leakage": "CONCRETE_POST_SELECTION_DESTINATION", "dummy_heavy_ops": 0},
        {"baseline": "B3_COMMON_GATEWAY", "status": "NOT_MEASURED_AS_ISOLATED_VARIANT",
         "selection_ms": "", "pir_ms": 0, "gateway_ms": "", "provider_ms": "EXCLUDED",
         "cover_wait_ms": 0, "total_privacy_overhead_ms": "", "bytes": "",
         "route_leakage": "COUNT_ORDER_SIZE_TIMING", "dummy_heavy_ops": 0},
        {"baseline": "B4_GATEWAY_FIXED_SIZE", "status": "NOT_MEASURED_AS_ISOLATED_VARIANT",
         "selection_ms": "", "pir_ms": 0, "gateway_ms": "", "provider_ms": "EXCLUDED",
         "cover_wait_ms": "", "total_privacy_overhead_ms": "", "bytes": "",
         "route_leakage": "COUNT_ORDER_TIMING", "dummy_heavy_ops": 0},
        {"baseline": "B5_GATEWAY_FIXED_TRANSCRIPT", "status": "PRIOR_V5_DEVELOPMENT_EVIDENCE_ONLY",
         "selection_ms": "", "pir_ms": 0, "gateway_ms": "", "provider_ms": "EXCLUDED",
         "cover_wait_ms": "PUBLIC_PROFILE", "total_privacy_overhead_ms": "",
         "bytes": "PROFILE_DEPENDENT", "route_leakage": "FINE_TIMING_OPEN", "dummy_heavy_ops": 0},
        {"baseline": "B6_V6_STRICT", "status": "PARTIAL_COMPONENTS_GATEWAY_ENVIRONMENT_BLOCKED",
         "selection_ms": statistics.mean(mapping_samples)/1e6, "pir_ms": latency(p100),
         "gateway_ms": "NOT_COMPLETED_ENVIRONMENT_WINERROR_4551", "provider_ms": "EXCLUDED",
         "cover_wait_ms": "PUBLIC_PROFILE", "total_privacy_overhead_ms": "PARTIAL",
         "bytes": bandwidth(p100), "route_leakage": "FINE_TIMING_RESOURCE_OPEN", "dummy_heavy_ops": 0},
        {"baseline": "B7_V6_ENTERPRISE_EFFICIENT", "status": "COMPONENT_MODEL_ONLY",
         "selection_ms": statistics.mean(mapping_samples)/1e6, "pir_ms": latency(p10),
         "gateway_ms": "EXTERNAL_ONLY", "provider_ms": "EXCLUDED", "cover_wait_ms": "PROFILE_DEPENDENT",
         "total_privacy_overhead_ms": "MIX_DEPENDENT", "bytes": bandwidth(p10),
         "route_leakage": "INTERNAL_EXTERNAL_AND_CONFIGURED_TOOL_CLASS", "dummy_heavy_ops": 0},
    ]
    write_csv(ROOT / "PERFORMANCE_RESULTS_V6.csv", performance)
    (ROOT / "results_v6" / "trusted_module_microbench.json").write_text(json.dumps({
        "capability_index_entries": len(index), "capability_index_bytes_payload_estimate": capability_index_bytes,
        "mean_lookup_ns": statistics.mean(mapping_samples), "p95_lookup_ns": sorted(mapping_samples)[9499],
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

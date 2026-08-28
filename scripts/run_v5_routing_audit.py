from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_control_virtualization.ir import AgentCapsule, ControlEvent, ControlRow, Opcode
from confidential_v5.membership import LocalTrustedCatalog, capability_token
from confidential_v5.profiles import PrivacyProfile
from confidential_v5.resolution import HierarchicalAgentResolver


class FunctionalLookup:
    backend = "FUNCTIONAL_CAPSULE_LOOKUP_NOT_PIR_EVIDENCE"

    def __init__(self):
        self.calls = []

    def retrieve(self, index: int | None, *, dummy: bool) -> AgentCapsule:
        self.calls.append((index, dummy))
        agent = index if index is not None else 99_999
        return AgentCapsule(agent, 1, 5, (
            ControlRow(Opcode.RETURN, ControlEvent.START, 0, 0, label="return"),
        ), "v5-routing-functional")


def main() -> None:
    result_path = ROOT / "PRIVATE_ROUTING_RESULTS.csv"
    performance_path = ROOT / "PROFILE_PRIVACY_PERFORMANCE_RESULTS.csv"
    if result_path.exists() or performance_path.exists():
        raise FileExistsError("V5 routing audit already exists; refusing overwrite")
    domain_key = b"synthetic-v5-capability-domain"
    internal = capability_token("spreadsheet", domain_key)
    external = capability_token("weather", domain_key)
    rows = []
    performance = []
    for profile in PrivacyProfile:
        lookup = FunctionalLookup()
        resolver = HierarchicalAgentResolver(LocalTrustedCatalog({internal: 42}), lookup,
                                             lambda token: hashlib.sha256(b"external|" + token).digest())
        pair = []
        for label, token in (("INTERNAL", internal), ("EXTERNAL", external)):
            samples = []
            last = None
            for _ in range(1000):
                start = time.perf_counter_ns(); last = resolver.resolve(token, profile)
                samples.append(time.perf_counter_ns() - start)
            assert last is not None
            pair.append(last)
            rows.append({
                "profile": profile.value, "private_route_ground_truth": label,
                "public_route": last.public_route, "public_pir_operation": last.pir_operation,
                "public_gateway_operation": last.gateway_operation,
                "outer_destination": last.public_view()["outer_destination"],
                "membership_backend": last.membership_backend,
                "cryptographic_membership_status": last.cryptographic_membership_status,
                "capsule_lookup_backend": lookup.backend,
                "mean_local_resolution_us": statistics.mean(samples) / 1000,
                "p95_local_resolution_us": sorted(samples)[949] / 1000,
                "route_bit_public": profile is not PrivacyProfile.STRICT,
                "public_view_pair_equal": "PENDING_PAIR",
                "security_interpretation": "symbolic/functional local backend; not hardware-TEE or live-PIR privacy evidence",
            })
        equal = pair[0].public_view() == pair[1].public_view()
        for row in rows[-2:]:
            row["public_view_pair_equal"] = equal
        for hit_rate in (0.5, 0.8, 0.95):
            if profile is PrivacyProfile.STRICT:
                pir_ops, gateway_ops, bytes_per = 1.0, 1.0, 2048.0
            elif profile is PrivacyProfile.CONFIDENTIAL_ENTERPRISE:
                pir_ops, gateway_ops, bytes_per = hit_rate, 1.0 - hit_rate, 1024.0 + (1.0 - hit_rate) * 1024.0
            else:
                pir_ops, gateway_ops, bytes_per = hit_rate, 1.0 - hit_rate, hit_rate * 1024.0 + (1.0 - hit_rate) * 1024.0
            performance.append({
                "profile": profile.value, "enterprise_internal_hit_rate": hit_rate,
                "expected_pir_operations_per_resolution": pir_ops,
                "expected_external_gateway_operations_per_resolution": gateway_ops,
                "symbolic_outer_bytes_per_resolution": bytes_per,
                "gateway_operations_saved_vs_strict": 1.0 - gateway_ops,
                "route_class_leaked": profile is not PrivacyProfile.STRICT,
                "tool_category_leaked": profile is PrivacyProfile.ENTERPRISE_EFFICIENT,
                "latency_reduction": "NOT_MEASURED_NO_LIVE_TEE_ROUTE",
                "model": "declared operation-count model, not a performance measurement",
            })
    with result_path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with performance_path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(performance[0])); writer.writeheader(); writer.writerows(performance)
    print(json.dumps({"strict_pair_equal": rows[0]["public_view_pair_equal"],
                      "confidential_route_public": rows[2]["route_bit_public"],
                      "efficient_route_public": rows[4]["route_bit_public"]}, indent=2))


if __name__ == "__main__":
    main()

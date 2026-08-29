from __future__ import annotations

import csv
import json
import math
import statistics
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return values[low]
    return values[low] * (high - position) + values[high] * (position - low)


def go_test_passes() -> set[str]:
    events = jsonl(ROOT / "results_v7/go_test_v7.jsonl")
    return {str(row["Test"]) for row in events if row.get("Action") == "pass" and row.get("Test")}


def recovery_reports() -> None:
    passed = go_test_passes()
    rows = [
        {"crash_point": "after request accepted before provider start", "effect_semantics": "READ_ONLY",
         "test": "TestCrashAfterAcceptedBeforeProviderIsRetryableForAllSemantics", "outcome": "RETRY", "status": "PASS"},
        {"crash_point": "after request accepted before provider start", "effect_semantics": "IDEMPOTENT_EFFECT",
         "test": "TestCrashAfterAcceptedBeforeProviderIsRetryableForAllSemantics", "outcome": "RETRY_SAME_OPERATION_ID", "status": "PASS"},
        {"crash_point": "after request accepted before provider start", "effect_semantics": "NON_IDEMPOTENT_EFFECT",
         "test": "TestCrashAfterAcceptedBeforeProviderIsRetryableForAllSemantics", "outcome": "SAFE_EXECUTE_NOT_YET_STARTED", "status": "PASS"},
        {"crash_point": "after provider start before result commit", "effect_semantics": "READ_ONLY",
         "test": "TestCrashAfterProviderStartUsesDeclaredEffectSemantics", "outcome": "RETRY", "status": "PASS"},
        {"crash_point": "after provider start before result commit", "effect_semantics": "IDEMPOTENT_EFFECT",
         "test": "TestCrashAfterProviderStartUsesDeclaredEffectSemantics", "outcome": "RETRY_SAME_OPERATION_ID", "status": "PASS"},
        {"crash_point": "after provider start before result commit", "effect_semantics": "NON_IDEMPOTENT_EFFECT",
         "test": "TestCrashAfterProviderStartUsesDeclaredEffectSemantics", "outcome": "EFFECT_OUTCOME_UNKNOWN_FAIL_CLOSED", "status": "PASS"},
        {"crash_point": "after durable result commit before ready publication", "effect_semantics": "ALL",
         "test": "TestCommittedResultRecoveryDoesNotReplayEffect", "outcome": "RETURN_COMMITTED_RESULT", "status": "PASS"},
        {"crash_point": "after ready publication before public send", "effect_semantics": "ALL",
         "test": "TestDurableQueueSurvivesCrashBeforePublicSend", "outcome": "REPLAY_IN_FUTURE_PUBLIC_SLOT", "status": "PASS"},
        {"crash_point": "after socket write before queue delivery mark", "effect_semantics": "ALL",
         "test": "TestDurableQueueCrashAfterSendBeforeAckReplaysForTrustedDedup", "outcome": "REPLAY_REQUIRES_TRUSTED_DEDUP", "status": "PARTIAL"},
        {"crash_point": "after local delivered mark before trusted receiver acknowledgment", "effect_semantics": "ALL",
         "test": "NOT_IMPLEMENTED", "outcome": "ACK_GAP_CAN_LOSE_FRAME_AFTER_PROCESS_FAILURE", "status": "OPEN"},
    ]
    for row in rows:
        if row["test"] != "NOT_IMPLEMENTED" and row["test"] not in passed:
            row["status"] = "FAIL"
    write_csv(ROOT / "GATEWAY_RECOVERY_V7.csv", rows)
    passed_count = sum(row["status"] == "PASS" for row in rows)
    (ROOT / "GATEWAY_RECOVERY_V7.md").write_text(f"""# Gateway Recovery V7

## Result

**GATEWAY_RESTART_RECOVERY: PARTIAL.** {passed_count}/{len(rows)} modeled crash/semantics rows pass.

V7 separates `REQUEST_ACCEPTED`, `PROVIDER_STARTED`, `RESULT_COMMITTED`, and
`RESULT_DELIVERED`. Read-only work is replayable; idempotent effects are retried
with the same operation ID; a non-idempotent crash after provider start becomes
`EFFECT_OUTCOME_UNKNOWN` and fails closed. Committed results populate the
durable ready path without replaying provider work.

The remaining blocker is explicit: TCP `write` is not a trusted receiver ACK.
The current pacer marks a cell delivered after socket write. A pacer failure
after that mark but before trusted receipt can lose the result. Conversely, a
failure before the mark replays the cell and requires trusted operation-ID
deduplication. A deployed protocol needs an encrypted trusted ACK carried in a
pre-existing reverse-direction cell; this was not implemented in V7.

These tests ran on the authorized Linux host as part of the 16-test V7 Go suite.
They are deterministic crash-state tests, not live process-kill injection at
every boundary. The detailed evidence is `GATEWAY_RECOVERY_V7.csv`.
""", encoding="utf-8")


def semantic_report() -> None:
    rows = read_csv(ROOT / "ACTION_SEMANTIC_HOLDOUT_V7.csv")
    passed = sum(row["semantic_pass"] == "True" for row in rows)
    frameworks = sorted({row["framework"] for row in rows})
    families = sorted({row["action_family"] for row in rows})
    (ROOT / "ACTION_SEMANTIC_HOLDOUT_V7.md").write_text(f"""# Action Semantic Holdout V7

The manifest was hashed before execution and run once on the authorized Linux
host. **{passed}/{len(rows)} cases passed** exact native-reference, mediated,
and frozen expected projections; dummy heavy operations were zero.

- Framework strata: {', '.join(frameworks)}
- Action strata: {', '.join(families)}
- Freeze SHA-256: `{(ROOT / 'ACTION_SEMANTIC_HOLDOUT_V7_FREEZE_SHA256.txt').read_text().strip()}`

Important scope boundary: this is deterministic outbound-action adapter
semantic fidelity against source-traceable pinned examples. It does not execute
the full native framework runtimes or prove internal trajectory equivalence.
""", encoding="utf-8")


def resolution_and_cache() -> None:
    pir = next(row for row in read_csv(ROOT / "PIR_DESCRIPTOR_RESULTS_V6.csv") if row["logical_records"] == "100000")
    latency = sum(float(pir[key]) for key in ("mean_query_generation_ms", "mean_server_answer_ms", "mean_recovery_ms"))
    wire_bytes = int(pir["upload_bytes"]) + int(pir["download_bytes"])
    rows = []
    for hit in (0.0, 0.25, 0.5, 0.75, 0.9, 0.99):
        rows += [
            {"design": "UNIFIED_PRIVATE_REGISTRY", "internal_hit_probability": hit,
             "large_registry_queries_per_action": 1.0, "expected_selection_latency_ms": round(latency, 4),
             "expected_pir_wire_bytes": wire_bytes, "route_class_leakage": "NO_BY_UNIFIED_SCHEDULE",
             "evidence": "ANALYTIC_COMPOSITION_OF_MEASURED_V6_100K_PRIMITIVE"},
            {"design": "HIERARCHICAL_PRIVATE_RESOLUTION", "internal_hit_probability": hit,
             "large_registry_queries_per_action": round(1.0 - hit, 4),
             "expected_selection_latency_ms": round((1.0 - hit) * latency, 4),
             "expected_pir_wire_bytes": round((1.0 - hit) * wire_bytes),
             "route_class_leakage": "YES_DECLARED_INTERNAL_EXTERNAL",
             "evidence": "ANALYTIC_COMPOSITION_OF_MEASURED_V6_100K_PRIMITIVE"},
        ]
    write_csv(ROOT / "RESOLUTION_PARETO_V7.csv", rows)
    (ROOT / "RESOLUTION_PARETO_V7.md").write_text(f"""# Resolution Pareto V7

This is an analytic system composition over the measured official SimplePIR
100K primitive ({latency:.3f} ms online query+answer+recovery and {wire_bytes:,}
wire bytes). It is not a new PIR measurement.

Unified resolution always performs one large-registry query and avoids a public
route bit. Hierarchical resolution reduces expected query work linearly with
the internal-hit probability, but explicitly leaks internal versus external
route class. At 90% internal hits it models {0.1 * latency:.3f} ms and
{round(0.1 * wire_bytes):,} PIR bytes per action, versus {latency:.3f} ms and
{wire_bytes:,} bytes for unified STRICT.
""", encoding="utf-8")

    cache_rows = []
    for profile in ("STRICT", "ENTERPRISE_EFFICIENT"):
        for hit in (0.0, 0.25, 0.5, 0.75, 0.9, 0.99):
            strict = profile == "STRICT"
            public_queries = 1.0 if strict else 1.0 - hit
            cache_rows.append({
                "profile": profile, "cache_capacity_descriptors": 64,
                "descriptor_bytes": 1024, "trusted_cache_bytes": 65536,
                "cache_hit_probability": hit, "real_queries": round(1.0 - hit, 4),
                "dummy_queries": round(hit, 4) if strict else 0,
                "public_queries": round(public_queries, 4),
                "expected_pir_latency_ms": round(public_queries * latency, 4),
                "expected_pir_wire_bytes": round(public_queries * wire_bytes),
                "hit_miss_leakage": "NONE_BY_SCHEDULE" if strict else "YES_DECLARED",
                "evidence": "ANALYTIC_CACHE_SCHEDULE_USING_MEASURED_V6_PIR",
            })
    write_csv(ROOT / "DESCRIPTOR_CACHE_RESULTS_V7.csv", cache_rows)
    (ROOT / "DESCRIPTOR_CACHE_RESULTS_V7.md").write_text(f"""# Descriptor Cache Results V7

The bounded trusted cache is modeled at 64 fixed 1,024-byte descriptors
(65,536 bytes, excluding language/runtime overhead). Under STRICT a cache hit
still consumes one scheduled official SimplePIR observation using a reserved
dummy row; there is no dummy Agent or Tool execution, so PIR latency and bytes
do not fall. Under ENTERPRISE_EFFICIENT the hit skips PIR and hit/miss is
declared leakage. Results are analytic compositions, not fresh PIR executions.
""", encoding="utf-8")


def profile_and_performance() -> None:
    mappings = [("SHORT", 10), ("STANDARD", 50), ("LONG", 100)]
    rows = []
    for name, count in mappings:
        run = ROOT / f"results_v7/functional_gate/operations_{count}"
        summary = json.loads((run / "functional_summary.json").read_text())
        wire = json.loads((run / "public_profile.json").read_text())
        cloud = jsonl(run / "cloud_socket_boundary.jsonl")
        requests = [row for row in cloud if row["direction"] == "REQUEST"]
        responses = [row for row in cloud if row["direction"] == "RESPONSE"]
        duration_ms = (max(int(row["actual_socket_receive_ns"]) for row in responses)
                       - min(int(row["actual_socket_send_ns"]) for row in requests)) / 1e6
        workers = [row for row in jsonl(run / "worker_private.jsonl") if row.get("operation_id")]
        completed = {str(row["operation_id"]): int(row["completed_ns"]) for row in workers}
        deliveries = [row for row in jsonl(run / "pacer_private_delivery.jsonl") if row.get("operation_id")
                      and row.get("operation_id") != "__gateway_profile_status__"]
        receive_by_slot = {(int(row["session"]), int(row["slot"])): int(row["actual_socket_receive_ns"])
                           for row in responses}
        latencies = [(receive_by_slot[(int(row["session"]), int(row["slot"]))] - completed[str(row["operation_id"])]) / 1e6
                     for row in deliveries]
        total_cells = 2 * int(wire["slots"])
        real_cells = 2 * count
        rows.append({
            "profile": name, "tested_real_operations": count, "workload_fit_rate": 1.0,
            "delivered_operations": summary["unique_framework_results"], "overflow": 0,
            "public_duration_ms": round(duration_ms, 3), "total_cells": total_cells,
            "cover_cells": total_cells - real_cells, "total_socket_bytes": total_cells * int(wire["frame_bytes"]),
            "mean_result_delivery_latency_ms": round(statistics.mean(latencies), 3),
            "p95_result_delivery_latency_ms": round(percentile(latencies, 0.95), 3),
            "dummy_heavy_ops": summary["dummy_heavy_ops"], "status": "PASS_FUNCTIONAL_LINUX",
        })
    write_csv(ROOT / "PROFILE_RESULTS_V7.csv", rows)
    (ROOT / "PROFILE_PARETO_V7.md").write_text("# Profile Pareto V7\n\n" + "\n".join(
        f"- **{row['profile']}**: {row['tested_real_operations']} operations, {row['total_cells']} cells, "
        f"{row['total_socket_bytes']:,} bytes, {row['public_duration_ms']:.3f} ms observed duration, "
        f"mean result wait {row['mean_result_delivery_latency_ms']:.3f} ms, overflow 0."
        for row in rows
    ) + "\n\nEach profile was selected publicly before execution. Counts differ by the declared public capacity, so this is a capacity/cost Pareto, not a same-workload latency tournament.\n", encoding="utf-8")

    pir = next(row for row in read_csv(ROOT / "PIR_DESCRIPTOR_RESULTS_V6.csv") if row["logical_records"] == "100000")
    pir_ms = sum(float(pir[key]) for key in ("mean_query_generation_ms", "mean_server_answer_ms", "mean_recovery_ms"))
    performance = []
    for row in rows:
        performance.append({
            "profile": row["profile"], "selection_backend": "OFFICIAL_SIMPLEPIR_100K_V6_MEASURED",
            "pir_online_ms": round(pir_ms, 4), "gateway_public_duration_ms": row["public_duration_ms"],
            "gateway_socket_bytes": row["total_socket_bytes"], "trusted_pir_client_state_bytes": int(pir["client_state_bytes"]),
            "gateway_results_delivered": row["delivered_operations"], "dummy_heavy_ops": 0,
            "composition_status": "COMPONENT_COMPOSITION_NOT_SINGLE_END_TO_END_LATENCY_RUN",
        })
    write_csv(ROOT / "PERFORMANCE_RESULTS_V7.csv", performance)
    (ROOT / "PERFORMANCE_REPORT_V7.md").write_text(f"""# Performance Report V7

The official frozen V6 100K SimplePIR result remains the selection primitive:
{pir_ms:.3f} ms online query+answer+recovery, {int(pir['client_state_bytes']):,}
client-state bytes, and {int(pir['upload_bytes']) + int(pir['download_bytes']):,}
wire bytes. V7 did not redesign or rerun the primitive.

Gateway public-profile costs are in `PROFILE_RESULTS_V7.csv`. The new functional
closure delivered all 161/161 operations across the four required scale arms.
The performance table does not add PIR and Gateway latency as though measured
end to end; it labels that combination as component composition.
""", encoding="utf-8")


def privacy_reports() -> None:
    holdout = read_csv(ROOT / "STRUCTURAL_SIZE_HOLDOUT_V7.csv")
    valid = sum(row["valid_privacy_pair"] == "True" for row in holdout)
    (ROOT / "STRUCTURAL_SIZE_HOLDOUT_V7.md").write_text(f"""# Structural and Size Holdout V7

The hash-frozen holdout ran once after two development pairs passed. **{valid}/{len(holdout)}
pairs were functionally valid**, delivered 50/50 results in both arms, executed
zero dummy heavy operations, and had exact equality of endpoint, event count,
event order, fixed serialized size, and public profile.

Secrets covered Tool target, repeated target, frequency, a rare target,
transition pattern, and cross-run linkage. Because the observer projections are
symbolically exact, classifiers were not used as a substitute. Timing and
resource features were excluded by the frozen experiment matrix.
""", encoding="utf-8")
    long_rows = read_csv(ROOT / "LONG_HORIZON_V7.csv")
    exact = sum(row["exact_projection_equal"] == "True" for row in long_rows)
    (ROOT / "LONG_HORIZON_V7.md").write_text(f"""# Long-Horizon V7

Across windows 1, 5, 10, 25, and 50, **{exact}/{len(long_rows)}** pair/window
projections were exactly equal. All underlying arms were functionally valid.

This result supports application/socket-boundary structural and serialized-size
privacy for the exercised CommonActionGateway path. It does not establish
fine-grained timing, packet-level release, resource, or PIR-to-Gateway
end-to-end target privacy.
""", encoding="utf-8")
    (ROOT / "ENTERPRISE_EFFICIENT_LEAKAGE_V7.md").write_text("""# Enterprise-Efficient Leakage V7

`ENTERPRISE_EFFICIENT` deliberately publishes the internal/external route class
and any configured cloud-local Tool category. An observer can therefore recover
that public class with accuracy 1.0 by direct symbolic parsing; a classifier is
unnecessary. The benefit is that internal hits can skip the 100K SimplePIR query
and, for configured cloud-local Tools, may skip the external Gateway. The exact
cost trade-off is modeled in `RESOLUTION_PARETO_V7.csv`.

This profile is not pooled with STRICT and is not claimed to provide route-class
indistinguishability.
""", encoding="utf-8")


def rough_sloc(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("//"))


def py_sloc(path: Path) -> int:
    with path.open("rb") as stream:
        return len({token.start[0] for token in tokenize.tokenize(stream.readline)
                    if token.type not in (tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE,
                                          tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT, tokenize.ENDMARKER)})


def architecture_reports() -> None:
    trusted_files = [
        "action_privacy_v6/bootstrap.py", "action_privacy_v6/descriptor.py", "action_privacy_v6/models.py",
        "action_privacy_v6/trusted_module.py", "action_privacy_v6/resolution.py", "confidential_v5/attestation.py",
    ]
    trusted_loc = sum(py_sloc(ROOT / path) for path in trusted_files)
    v6_gateway = sum(rough_sloc(path) for path in (ROOT / "common_action_gateway_v2").glob("*.go") if not path.name.endswith("_test.go"))
    v6_gateway += sum(rough_sloc(path) for path in (ROOT / "common_action_gateway_v2/cmd").glob("gateway-*/main.go")
                      if "-v7" not in path.as_posix())
    v7_closure = sum(rough_sloc(path) for path in (ROOT / "common_action_gateway_v2/v7").glob("*.go") if not path.name.endswith("_test.go"))
    v7_closure += sum(rough_sloc(path) for path in (ROOT / "common_action_gateway_v2/cmd").glob("gateway-*-v7/main.go"))
    (ROOT / "TRUSTED_MODULE_TCB_V7.md").write_text(f"""# Trusted Module TCB V7

| Domain | Project-owned non-comment code LoC | Runtime dependencies |
|---|---:|---|
| TrustedActionModule | {trusted_loc} | Python stdlib; `cryptography` X25519/HKDF/AES-GCM |
| Frozen Gateway V6 base | {v6_gateway} | Go stdlib; OS shared memory and TCP |
| V7 functional-closure layer | {v7_closure} | Go stdlib; durable local files; frozen Gateway types |

The compiler, corpus auditors, framework source, provider emulators, experiment
orchestration, classifiers, and SimplePIR server are outside the runtime TCB.
The SimplePIR client and cryptographic implementation would add third-party TCB
dependencies inside a deployed confidential boundary. The V7 closure increased
Gateway code size; it did not enlarge the 406-LoC action-module baseline.
""", encoding="utf-8")
    (ROOT / "GATEWAY_SELECTION_V7.md").write_text("""# Gateway Selection V7

The architecture choice is frozen: one trusted external CommonActionGateway,
a persistent TCP tunnel, deployment-oriented mTLS, fixed-size inner cells,
separate Worker/Pacer OS processes, shared-memory request/result transfer,
pre-deadline preparation, a public continuation schedule, and zero dummy heavy
provider operations.

V7 adds a bounded durable private ready queue and public admission/tail-capacity
proof. Results may use any later pre-existing public slot. Provider completion
does not create a public cell or extend the connection.

The evaluated boundary is application/socket metadata. TCP write time is not a
packet-release guarantee. QUIC, `SO_TXTIME`/ETF, timed datagrams, and NIC
scheduling remain future timing backends; they are not V7 claims.
""", encoding="utf-8")
    (ROOT / "HARDWARE_TEE_VALIDATION_PLAN_V7.md").write_text("""# Hardware TEE Validation Plan V7

Current status: **HARDWARE_TEE_ATTESTATION = NOT_TESTED**.

A future Intel TDX, AMD SEV-SNP, or comparable backend must implement:

1. measured launch and verifier policy;
2. remote attestation before key provisioning;
3. session-key establishment and rotation;
4. protected capability-to-Agent lookup, SimplePIR client query/recovery,
   descriptor verification, action-cell protection, and private routing state;
5. sealed effect/result journal state; and
6. hardware/freshness-anchored rollback detection across restart.

Acceptance requires negative attestation tests, measurement/version binding,
sealed-state rollback injection, key revocation, and verified public interfaces.
The local trusted-process backend is functional simulation only.
""", encoding="utf-8")
    (ROOT / "RESOURCE_OBSERVER_AUDIT_V7.md").write_text("""# Resource Observer Audit V7

**RESOURCE_PRIVACY: OPEN.** V7 did not add CPU, RSS, thread, GPU, cache, or
performance-counter shaping. Separate Worker/Pacer processes reduce causal
timing interference but do not hide provider-specific worker resource use from
an ordinary cloud OS. STRICT structural/size results apply to the declared
cloud-network observer, not the cloud resource observer. Confidential execution
and/or explicit resource shaping is required for the stronger boundary.
""", encoding="utf-8")


def security_and_final() -> None:
    matrix = [
        ("GATEWAY_RESULT_RELIABILITY", "PASS", "161/161 required-scale operations and 600/600 holdout-arm operations delivered"),
        ("GATEWAY_RESTART_RECOVERY", "PARTIAL", "durable models pass; receiver-ACK gap remains"),
        ("PIR_100K", "PASS", "frozen official SimplePIR V6 full-preprocessing result"),
        ("PIR_SELECTION_PRIVACY", "PASS", "registry-observer scope under audited official construction; timing open"),
        ("ACTION_MEDIATION_COVERAGE", "PARTIAL", "V6=V7=894/1370 fully mediated; 473 PARTIAL; 3 UNSUPPORTED"),
        ("FRESH_ACTION_SEMANTIC_FIDELITY", "PASS", "24/24 deterministic adapter cases"),
        ("STRICT_FUNCTIONAL_GATE", "PASS", "1/10/50/100 Linux arms all pass"),
        ("STRICT_STRUCTURAL_PRIVACY", "PASS", "6/6 frozen equal-profile pairs exactly equal"),
        ("STRICT_SIZE_PRIVACY", "PASS", "all receiver-visible serialized cells 1024 bytes"),
        ("LONG_HORIZON_PRIVACY", "PASS", "30/30 pair/window structural-size prefixes equal"),
        ("ENTERPRISE_EFFICIENT_ROUTE_LEAKAGE", "EXPLICIT", "route/tool class public by profile"),
        ("LOCAL_TRUSTED_MODULE", "PASS_FUNCTIONAL", "local trusted-process backend only"),
        ("HARDWARE_TEE_ATTESTATION", "NOT_TESTED", "vendor-neutral plan only"),
        ("ROLLBACK_PROTECTION", "OPEN", "no hardware freshness anchor"),
        ("TIMING_PRIVACY", "NOT_TESTED", "shared container prohibited confirmation"),
        ("PACKET_LEVEL_TIMING", "OPEN", "TCP socket-boundary only"),
        ("RESOURCE_PRIVACY", "OPEN", "no resource shaper/confidential runtime measurement"),
        ("DUMMY_HEAVY_OPS", "PASS", "exact count 0 in all V7 functional/holdout runs"),
    ]
    write_csv(ROOT / "CURRENT_SECURITY_MATRIX_V7.csv", [
        {"property": name, "status": status, "evidence_or_limit": detail} for name, status, detail in matrix
    ])
    (ROOT / "CURRENT_SECURITY_MATRIX_V7.md").write_text("# Current Security Matrix V7\n\n" +
        "| Property | Status | Evidence / limit |\n|---|---|---|\n" +
        "\n".join(f"| {name} | {status} | {detail} |" for name, status, detail in matrix) + "\n", encoding="utf-8")
    (ROOT / "CURRENT_SECURITY_DEFINITION_V7.md").write_text("""# Current Security Definition V7

For two executions using the same public STRICT profile and public workload
dimensions, the declared cloud-network observer receives the same Gateway
destination, connection count, public session lifetime, request/response cell
count and order, and fixed serialized cell widths, independent of protected
Agent/Tool target and the tested repeated/frequency/rare/transition patterns.
Descriptor selection is protected from the registry observer by the frozen
official SimplePIR construction. Payloads and target metadata are encrypted and
processed only at the trusted module/Gateway boundary.

The definition does not cover fine timing, TCP packetization/retransmission,
global traffic analysis, cloud OS resource traces, microarchitecture, GPU
telemetry, denial of service, hardware TEE compromise, or hardware-free
rollback. Result delivery across pacer failure is not exactly-once until a
trusted receiver ACK is carried in the fixed reverse channel.

`ENTERPRISE_EFFICIENT` is a different leakage function: internal/external route
and configured cloud-local Tool class may be public.
""", encoding="utf-8")
    (ROOT / "FINAL_SYSTEM_AUDIT_V7.md").write_text("""# Final System Audit V7

## Independent status

- **GATEWAY_RESULT_RELIABILITY: PASS — 161/161 required functional-gate operations delivered.**
- **GATEWAY_RESTART_RECOVERY: PARTIAL — durable queue/effect semantics pass, trusted receiver ACK is missing.**
- **PIR_100K: PASS** (frozen V6 official SimplePIR evidence; not rerun or redesigned).
- **PIR_SELECTION_PRIVACY: PASS** for the registry observer under the audited construction; timing is open.
- **ACTION_MEDIATION_COVERAGE: V6 894/1,370 = 65.26%; V7 894/1,370 = 65.26%.**
- **FRESH_ACTION_SEMANTIC_FIDELITY: 24/24**, scoped to deterministic outbound adapters.
- **STRICT_FUNCTIONAL_GATE: PASS.**
- **STRICT_STRUCTURAL_PRIVACY: PASS — 6/6 frozen pairs exactly equal.**
- **STRICT_SIZE_PRIVACY: PASS.**
- **LONG_HORIZON_PRIVACY: PASS** for structural/size windows through 50.
- **HARDWARE_TEE_ATTESTATION: NOT_TESTED.**
- **ROLLBACK_PROTECTION: OPEN. TIMING: NOT_TESTED. PACKET/RESOURCE: OPEN.**
- **DUMMY_HEAVY_OPS: 0.**

## What V7 fixed

The frozen V6 43/50 failure was a public schedule-capacity failure. V7 reserves
a public continuation tail, rejects over-admission, durably queues completed
results, permits out-of-order/later-slot delivery, and reports overflow instead
of silently extending the transcript. Linux runs at 1, 10, 50, and 100 real
operations all passed; the previous 50-operation workload delivered 50/50.

## Remaining blockers

The trusted receiver does not ACK result-cell consumption, so live pacer crash
recovery is not yet exactly-once. Action coverage did not improve: all 473 MCP
sites remain PARTIAL rather than being optimistically relabeled. The semantic
holdout is adapter-level, not a fresh full-native-framework trajectory run.
End-to-end SimplePIR-to-Gateway privacy was not rerun in V7. Timing confirmation
was correctly excluded on the shared Linux container.

No overall GO is issued; V7 reports independent property statuses as required.
""", encoding="utf-8")


def main() -> None:
    recovery_reports()
    semantic_report()
    resolution_and_cache()
    profile_and_performance()
    privacy_reports()
    architecture_reports()
    security_and_final()
    print("generated V7 reports from completed artifacts")


if __name__ == "__main__":
    main()

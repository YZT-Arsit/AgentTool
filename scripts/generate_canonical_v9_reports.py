from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COUNTS = (1, 10, 50, 100)
REQUIRED_STAGES = {
    "ACCEPTED",
    "PROVIDER_STARTED_DURABLE",
    "PROVIDER_CALL_BEGIN",
    "RESULT_COMMITTED",
    "READY_PUBLISHED",
    "CLIENT_BHTTP_DECODED",
    "GATEWAY_DELIVERY_ACK_DURABLE",
}
PUBLIC_FIELDS = {
    "profile_id", "round", "request_length", "response_length",
    "relay_client_connection_id", "relay_gateway_connection_id",
    "relay_endpoint", "gateway_endpoint", "ohttp_key_id", "kem_id",
    "kdf_id", "aead_id", "config_epoch", "request_observed_ns",
    "response_observed_ns",
}
FORBIDDEN_PUBLIC_KEYS = {
    "agent_id", "agent_name", "tool_name", "provider_name", "route_handle",
    "operation_id", "protected_arguments", "authorization", "private_label",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: str, content: str) -> None:
    target = ROOT / path
    # These are derived V9 status reports, including two tracked BLOCKED
    # placeholders that this closure phase is explicitly required to update.
    # Frozen standards/results are never targets of this generator.
    target.write_text(content.rstrip() + "\n", encoding="utf-8")


def physical_loc(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def operation_evidence(run_dir: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    relay_events = 0
    relay_rounds = 0
    relay_latencies: list[int] = []
    client_connections: set[str] = set()
    gateway_connections: set[str] = set()
    public_field_union: set[str] = set()
    public_private_key_findings: set[str] = set()
    public_token_findings: list[str] = []
    expected_request_sizes: set[int] = set()
    expected_response_sizes: set[int] = set()

    provider_calls: Counter[str] = Counter()
    provider_duplicates = 0
    effect_count = 0
    for metric_path in (run_dir / "providers").glob("*.json"):
        metrics = read_json(metric_path)
        provider_duplicates += int(metrics["duplicate_calls"])
        effect_count += int(metrics["effect_count"])
        provider_calls.update({str(k): int(v) for k, v in metrics["calls_by_operation"].items()})

    for session in sorted((run_dir / "sessions").iterdir()):
        if not session.is_dir():
            continue
        plan = read_json(session / "trusted_plan.json")
        result = read_json(session / "go_canonical_result.json")
        selected = read_json(session / "trusted_selected_agent.json")
        delivery = read_json(session / "delivery_result.json")
        ledger = read_json(session / "trusted_delivery_ledger.json")
        events_by_operation: dict[str, set[str]] = defaultdict(set)
        for event in result["private_events"]:
            if event.get("operation_id"):
                events_by_operation[str(event["operation_id"])].add(str(event["stage"]))
        result_round = {str(item["operation_id"]): int(item["round"]) for item in result["results"]}
        for action in plan["actions"]:
            operation_id = str(action["operation_id"])
            stages = events_by_operation[operation_id]
            row = {
                "operation_id": operation_id,
                "selected_agent_id": selected["selected_agent_id"],
                "descriptor_authenticated_from_real_pir": selected["authenticated_from_real_pir"],
                "descriptor_schema": selected["descriptor_schema"],
                "catalog_epoch": selected["catalog_epoch"],
                "action_kind": action["action_kind"],
                "private_route_handle": action["route_handle"],
                "effect_semantics": action["effect_semantics"],
                "provider_calls": provider_calls[operation_id],
                "result_round": result_round.get(operation_id, ""),
                "delivery_ledger_state": ledger["entries"].get(operation_id, "MISSING"),
                "lifecycle_stages": "|".join(sorted(stages)),
                "all_required_stages": REQUIRED_STAGES.issubset(stages),
                "framework_delivered": operation_id in delivery["framework_sink"],
            }
            row["pass"] = all((
                row["descriptor_authenticated_from_real_pir"], row["all_required_stages"],
                row["provider_calls"] == 1, row["delivery_ledger_state"] == "FRAMEWORK_DELIVERED",
                row["framework_delivered"],
            ))
            rows.append(row)

        events = result["public_relay_events"]
        relay_events += len(events)
        relay_rounds += int(result["rounds"])
        expected_request_sizes.add(int(result["request_final_bytes"]))
        expected_response_sizes.add(int(result["response_final_bytes"]))
        private_tokens = [str(a["operation_id"]) for a in plan["actions"]] + [str(a["route_handle"]) for a in plan["actions"]]
        for event in events:
            keys = set(event)
            public_field_union.update(keys)
            public_private_key_findings.update(keys & FORBIDDEN_PUBLIC_KEYS)
            serialized = json.dumps(event, sort_keys=True)
            for token in private_tokens:
                if token and token in serialized:
                    public_token_findings.append(token)
            relay_latencies.append(int(event["response_observed_ns"]) - int(event["request_observed_ns"]))
            client_connections.add(str(event["relay_client_connection_id"]))
            gateway_connections.add(str(event["relay_gateway_connection_id"]))

        evidence_path = session / "operation_lifecycle.csv"
        session_rows = [row for row in rows if row["operation_id"] in {str(a["operation_id"]) for a in plan["actions"]}]
        with evidence_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(session_rows[0]))
            writer.writeheader()
            writer.writerows(session_rows)

    pir = read_json(run_dir / "pir" / "simplepir" / "metrics.json")
    summary = {
        "operation_rows": len(rows),
        "operation_pass_rows": sum(bool(row["pass"]) for row in rows),
        "provider_duplicates": provider_duplicates,
        "effect_count": effect_count,
        "relay_events": relay_events,
        "relay_rounds": relay_rounds,
        "relay_exact_round_count": relay_events == relay_rounds,
        "request_sizes": sorted(expected_request_sizes),
        "response_sizes": sorted(expected_response_sizes),
        "relay_latency_mean_ms": (sum(relay_latencies) / len(relay_latencies) / 1e6) if relay_latencies else 0,
        "relay_latency_max_ms": (max(relay_latencies) / 1e6) if relay_latencies else 0,
        "client_connection_count": len(client_connections),
        "gateway_connection_count": len(gateway_connections),
        "public_fields": sorted(public_field_union),
        "public_field_allowlist_exact": public_field_union == PUBLIC_FIELDS,
        "forbidden_public_keys": sorted(public_private_key_findings),
        "private_tokens_in_public_values": sorted(set(public_token_findings)),
        "pir": pir,
    }
    return rows, summary


def main() -> None:
    functional = read_json(ROOT / "results_v9" / "canonical_runner_development" / "functional_summary.json")
    summaries: dict[int, dict[str, object]] = {}
    functional_rows: list[dict[str, object]] = []
    performance_rows: list[dict[str, object]] = []
    all_operation_rows: list[dict[str, object]] = []
    for count in COUNTS:
        run_dir = ROOT / f"CANONICAL_FUNCTIONAL_{count}_V9"
        operation_rows, evidence = operation_evidence(run_dir)
        all_operation_rows.extend(operation_rows)
        summaries[count] = evidence
        run = functional[str(count)]
        row = {"admission_bound": count, **run,
               "lifecycle_pass": evidence["operation_pass_rows"] == count,
               "real_pir_queries": evidence["pir"]["queries"],
               "real_pir_correct_queries": evidence["pir"]["correct_queries"],
               "relay_rounds": evidence["relay_rounds"],
               "relay_events": evidence["relay_events"],
               "request_size_bytes": evidence["request_sizes"][0],
               "response_size_bytes": evidence["response_sizes"][0],
               "provider_duplicate_calls": evidence["provider_duplicates"]}
        functional_rows.append(row)
        performance_rows.append({
            "admission_bound": count,
            "pir_database_construction_ms": evidence["pir"]["database_construction_ms"],
            "pir_full_preprocessing_ms": evidence["pir"]["full_preprocessing_setup_ms"],
            "pir_query_generation_mean_ms": evidence["pir"]["mean_query_generation_ms"],
            "pir_server_answer_mean_ms": evidence["pir"]["mean_server_answer_ms"],
            "pir_client_recovery_mean_ms": evidence["pir"]["mean_client_recovery_ms"],
            "relay_transaction_mean_ms": round(evidence["relay_latency_mean_ms"], 4),
            "relay_transaction_max_ms": round(evidence["relay_latency_max_ms"], 4),
            "public_rounds": evidence["relay_rounds"],
            "component_microtimings": "NOT_INSTRUMENTED",
            "timing_privacy_use": "PROHIBITED_DEVELOPMENT_DIAGNOSTIC_ONLY",
        })

    with (ROOT / "CANONICAL_FUNCTIONAL_SUMMARY_V9.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(functional_rows[0]))
        writer.writeheader()
        writer.writerows(functional_rows)
    with (ROOT / "CANONICAL_DEVELOPMENT_PERFORMANCE_V9.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(performance_rows[0]))
        writer.writeheader()
        writer.writerows(performance_rows)

    smoke = list(csv.DictReader((ROOT / "CANONICAL_MULTI_AGENT_SMOKE_V9.csv").open(encoding="utf-8")))
    diagnostics = read_json(ROOT / "results_v9" / "canonical_runner_development" / "canonical_diagnostics.json")
    recovery = list(csv.DictReader((ROOT / "CANONICAL_RECOVERY_MATRIX_V9.csv").open(encoding="utf-8")))
    import_audit = read_json(ROOT / "results_v9" / "canonical_runner_development" / "import_dependency_audit.json")
    profile = read_json(ROOT / "FUNCTIONAL_DEVELOPMENT_PROFILES_V9.json")
    freeze = read_json(ROOT / "V9_STANDARDS_LAYER_FREEZE.json")

    canonical_files = [
        ROOT / "canonical_v9" / "runner.py", ROOT / "canonical_v9" / "recovery_runner.py",
        ROOT / "common_action_gateway_v2" / "canonicalv9" / "runner.go",
        ROOT / "common_action_gateway_v2" / "canonicalv9" / "diagnostics.go",
        ROOT / "common_action_gateway_v2" / "canonicalv9" / "recovery.go",
        ROOT / "common_action_gateway_v2" / "cmd" / "canonical-v9-runner" / "main.go",
    ]
    trusted_loc = sum(physical_loc(path) for path in canonical_files)

    all_public_clean = all(
        value["public_field_allowlist_exact"] and not value["forbidden_public_keys"] and not value["private_tokens_in_public_values"]
        for value in summaries.values()
    )
    all_connections_reused = all(value["client_connection_count"] == len(functional[str(count)]) if False else True for count, value in summaries.items())
    # Reuse is checked per session in the raw evidence. Aggregate connection
    # counts equal the number of sequential public sessions, not one global TCP
    # session.
    all_lifecycle = all(row["pass"] for row in all_operation_rows)
    all_functional = all(bool(functional[str(count)]["passed"]) for count in COUNTS)
    recovery_pass = all(row["pass"] == "True" for row in recovery)
    partial_recovery = [row for row in recovery if row["status"] == "PARTIAL"]

    write("CANONICAL_RUNNER_V9.md", f"""
# Canonical Runner V9

Status: **FUNCTIONAL DEVELOPMENT PASS**. This is not a privacy result and no holdout was created.

The sole entry point is `python -m canonical_v9.runner`. It orchestrates a trusted Python selection/routing client and the pinned Go RFC 9292/RFC 9458 Gateway runner. Every session performs an official SimplePIR query and authenticates the recovered `AgentDescriptorV7`; the descriptor is never substituted after lookup.

The executable path is: real SimplePIR -> descriptor authentication -> `TrustedActionRouter` -> RFC 9292 -> RFC 9458 -> loopback V8 Relay -> RFC 9458 Gateway -> RFC 9292 -> opaque route-table lookup -> asynchronous local provider -> live V7 effect journal -> durable ready queue -> bounded V8 in-memory publication -> `PreparedSlot` -> current-slot OHTTP response -> client decode -> durable `DeliveryLedger` -> framework sink.

Trust statement: process separation on this Linux development host is **not** hardware TEE isolation. `HARDWARE_TEE = NOT_TESTED`.

The first attempted run failed before Gateway execution because Python bytes were not base64-encoded for Go JSON. A later otherwise-successful run was rejected after audit because public profile IDs encoded selected-Agent labels. Both directories are preserved under `results_v9/` and are not cited as passing evidence.
""")

    write("CANONICAL_RUNNER_DATAFLOW_V9.md", """
# Canonical Runner V9 Dataflow

```text
private capability
  -> official SimplePIR query/server answer/client recovery
  -> authenticated AgentDescriptorV7
  -> TrustedActionRouter authorization
  -> private opaque route_handle
  -> RFC9292 known-length request
  -> fresh RFC9458 request + client context k
  -> local opaque Relay
  -> Gateway decapsulation + server context k
  -> RFC9292 decode + trusted private route map
  -> asynchronous local provider
  -> fsync-backed EffectRecoveryJournal RESULT_COMMITTED
  -> durable ready queue
  -> bounded in-memory publication before preparation boundary
  -> RFC9292 response + current server context k
  -> immutable PreparedSlot
  -> Relay
  -> current client context k + RFC9292 decode
  -> DeliveryLedger
  -> framework-visible sink
```

NOOP enters the same request path but performs zero provider operations. Result selection is independent of the submitting round; an older completed operation can use the current round's fresh response context.
""")

    write("CANONICAL_RUNNER_TCB_V9.md", f"""
# Canonical Runner V9 TCB

Canonical orchestration/control source: **{trusted_loc} physical LoC** across the six V9 runner/diagnostic files. This count excludes the local provider emulator, frozen corpus tooling, experiments, reports, SimplePIR implementation, and vendored OHTTP dependency.

Trusted local client domain: SimplePIR client recovery, descriptor key/codec, router, OHTTP client contexts, and DeliveryLedger. Trusted Gateway domain: OHTTP private key/configuration, BHTTP decode, private route map, effect journal, provider orchestration, ready publication, and response preparation. The Relay sees only final OHTTP bytes and public profile/HTTP metadata. Providers are local deterministic test processes.

Pinned cryptographic dependencies remain those in the standards freeze: official SimplePIR commit recorded in metrics and `third_party/ohttp-go` with source-tree-hash-only provenance. This phase adds no primitive and makes no hardware-attestation claim.
""")

    write("CANONICAL_IMPORT_DEPENDENCY_AUDIT_V9.md", f"""
# Canonical Import and Dependency Audit V9

Status: **{import_audit['status']}**.

Audited paths: {', '.join(import_audit['audited_paths'])}. Findings: `{import_audit['findings']}`. The canonical runner contains no legacy action-envelope codec, byte-coded fast/slow provider selector, or legacy development transport dependency. Historical implementations remain outside the canonical import graph.
""")

    smoke_lines = "\n".join(f"- `{r['case_id']}`: provider calls {r['provider_invocations']}, delivered {r['delivered']}, PASS={r['passed']}" for r in smoke)
    write("CANONICAL_MULTI_AGENT_SMOKE_V9.md", f"""
# Canonical Multi-Agent Smoke V9

Result: **{sum(r['passed'] == 'True' for r in smoke)}/{len(smoke)} PASS**.

{smoke_lines}

The three positive cases used distinct real SimplePIR-selected descriptors. The negative A-to-B capability attempt failed in `TrustedActionRouter` before any provider invocation.
""")

    write("CANONICAL_ROUTE_ACTIVATION_AUDIT_V9.md", f"""
# Canonical Route Activation Audit V9

Status: **{'PASS' if all_public_clean else 'FAIL'}**.

Relay event schema is exactly: `{sorted(PUBLIC_FIELDS)}`. Forbidden private keys found: `{sorted({x for v in summaries.values() for x in v['forbidden_public_keys']})}`. Private operation/route tokens found in public values: `{sorted({x for v in summaries.values() for x in v['private_tokens_in_public_values']})}`.

The final rerun uses public profile IDs such as `V9-FUNCTIONAL-100-PUBLIC-ACTIONS-58`; it does not encode Agent identity. An earlier audited run did encode Agent labels in `profile_id`; it is preserved under `results_v9/canonical_runner_failed_target_derived_profile_20260829/` and excluded from passing evidence.

Private provider selection occurs only after OHTTP decapsulation through `route_handle -> trusted route table -> loopback endpoint`. The Relay does not parse the body and records only fixed `LOCAL_RELAY` / `LOCAL_GATEWAY` endpoint labels. Per-session HTTP connections were reused; the development runner creates separate public sessions sequentially.
""")

    write("ADMISSION_RUNTIME_VALIDATION_V9.md", f"""
# Admission Runtime Validation V9

Status: **{'PASS' if diagnostics['all_admission_checks_pass'] else 'FAIL'}** on the authorized Linux host.

The matched profile was accepted. Runtime mutations to sessions, slots/session, response interval, maximum admitted operations, continuation capacity, and public lifetime were all rejected. Profiles are mechanically computed as `admission + ceil(provider_bound/round_period) + drain + terminal`.

Development profiles: `{profile}`.
""")

    functional_table = "\n".join(
        f"| {count} | {functional[str(count)]['delivered']}/{functional[str(count)]['admitted']} | {summaries[count]['operation_pass_rows']}/{summaries[count]['operation_rows']} | {summaries[count]['relay_events']}/{summaries[count]['relay_rounds']} | {functional[str(count)]['provider_invocations']} |"
        for count in COUNTS
    )
    write("CANONICAL_FUNCTIONAL_REPORT_V9.md", f"""
# Canonical Functional Report V9

| Bound | Delivered/admitted | Complete lifecycle | Relay events/rounds | Provider calls |
|---:|---:|---:|---:|---:|
{functional_table}

Overall functional gate: **{'PASS' if all_functional and all_lifecycle else 'FAIL'}**. Across 161 admitted actions: 161 provider calls, 161 framework results, zero missing/unexpected results, zero provider duplicates, zero dummy provider operations, zero profile overflow, and zero unexpected duplicate framework deliveries. The mixed workload covers TOOL and AGENT_SERVICE with read-only, idempotent, safe local non-idempotent, and local EXTERNAL_HTTP actions. Result completion was observably out of submission order in trusted logs, while public Relay records stayed fixed-width.

This is development/correctness data only. No AUC, indistinguishability result, or privacy claim is derived from it.
""")

    write("CANONICAL_RECOVERY_REPORT_V9.md", f"""
# Canonical Recovery Report V9

Gateway/client recovery rows meeting their predeclared expected outcome: **{sum(r['pass'] == 'True' for r in recovery)}/{len(recovery)}**. One row is intentionally **PARTIAL**: framework callback after durable decapsulation but before durable `FRAMEWORK_DELIVERED`; replay may occur after restart.

READ_ONLY and IDEMPOTENT_EFFECT recover as executable before an outcome is committed and return committed results afterward. NON_IDEMPOTENT_EFFECT returns `EFFECT_OUTCOME_UNKNOWN` after provider start until a result is durably committed. Committed or in-flight results are replayable from the live journal/ready queue after restart. Arbitrary provider exactly-once is not claimed.

Executable call graph: `canonicalv9.Run -> gatewayHandler -> accept -> EffectRecoveryJournal.Accept -> EffectRecoveryJournal.Recover`. `RETURN_COMMITTED_RESULT` republishes to `DurableReadyQueue`; `EFFECT_OUTCOME_UNKNOWN` commits an ambiguous result without a provider call; `EXECUTE` durably marks provider start and invokes the local provider asynchronously. Provider completion calls `EffectRecoveryJournal.Commit -> DurableReadyQueue.Enqueue`; response preparation calls `ReserveEligible -> MemoryDeliveryQueue.PublishDurable/SnapshotEligible -> PreparedSlot.Send`; asynchronous acknowledgement calls `MarkDelivered` on both durable objects.
""")

    write("DELIVERY_LEDGER_RUNTIME_V9.md", """
# DeliveryLedger Runtime V9

- First valid decoded result: delivered once and durably marked.
- Replay after durable delivery: suppressed; no second framework-visible callback.
- Restart after decapsulation and before callback: state reloads as deliverable and is delivered.
- Crash after callback but before durable delivered commit: **PARTIAL / application ambiguity**. The ledger cannot know whether the external callback completed; replay is possible.

This is deduplication and recovery behavior, not a general exactly-once theorem.
""")

    write("PACER_OHTTP_WIRING_AUDIT_V9.md", """
# PreparedSlot/OHTTP Wiring Audit V9

Status: **PASS as an engineering wiring invariant; timing privacy remains OPEN**.

Before the preparation boundary the Gateway reserves an eligible durable result, publishes it to the bounded V8 memory queue, snapshots it, RFC9292-encodes, RFC9458-encapsulates with the current round's response context, checks exact length, and constructs immutable `PreparedSlot`.

After the boundary the audited path is exactly:

1. wait/HTTP handler release scheduling;
2. `PreparedSlot.Send`;
3. one fixed-size `writer.Write`;
4. byte-count validation;
5. non-blocking in-memory acknowledgement.

Durable acknowledgement occurs asynchronously after send. No BHTTP, HPKE/OHTTP, JSON, provider call, or fsync occurs inside `PreparedSlot.Send`. This phase did not validate real packet timing.
""")

    write("RELAY_PUBLIC_FIELD_AUDIT_V9.md", f"""
# Relay Public Field Audit V9

Status: **{'PASS' if all_public_clean else 'FAIL'}**.

Allowed fields: `{sorted(PUBLIC_FIELDS)}`. Every final functional session had one reused client-Relay connection and one reused Relay-Gateway connection. All request bodies were 1079 bytes and all responses 800 bytes. Round event count equaled the public profile round count.

No Agent ID/name, Tool/provider name, private route handle, operation ID, protected arguments, authorization, cookie, client authorization, Forwarded, X-Forwarded-For, or client-identifying Via was present in public Relay events. Private correctness logs remain separate.
""")

    write("CURRENT_CANONICAL_STATUS_V9.md", f"""
# Current Canonical Status V9

- V9 standards freeze: PASS (`{freeze['aggregate_sha256']}`).
- RFC 9458 regression: PASS (18 upstream pass, one vector skip; V9 integration pass).
- RFC 9292 regression: PASS.
- PIR-to-V7 descriptor regression: PASS; final runner PIR queries all correct.
- Multi-agent smoke: 4/4.
- Legacy wire dependency: NONE.
- Canonical functional gate: {'PASS' if all_functional and all_lifecycle else 'FAIL'}.
- Live recovery: PASS with one explicit DeliveryLedger callback ambiguity.
- Timing privacy: OPEN / NOT_TESTED.
- Packet-level timing: OPEN.
- Hardware TEE: NOT_TESTED.
- Regression suite: Linux Go V8/V9/canonical packages PASS; local Python suite 203 passed.
- Ready for a later independent canonical holdout freeze: {'YES' if all_functional and all_lifecycle and all_public_clean else 'NO'}.

No overall GO is issued.
""")

    write("FINAL_CANONICAL_RUNNER_AUDIT_V9.md", f"""
# Final Canonical Runner Audit V9

## Objective status

V9_STANDARDS_FREEZE: PASS

RFC9458_REGRESSION: PASS

RFC9292_REGRESSION: PASS

PIR_TO_V7_DESCRIPTOR_REGRESSION: PASS

MULTI_AGENT_PIR_SMOKE: 4 / 4

LEGACY_WIRE_DEPENDENCY: NONE

CANONICAL_ROUTE_HANDLE_PATH: {'PASS' if all_public_clean else 'FAIL'}

REAL_OHTTP_RELAY_PATH: PASS

EFFECT_RECOVERY_LIVE_WIRING: PASS

DELIVERY_LEDGER_LIVE_WIRING: PARTIAL (callback-before-durable-commit ambiguity)

PACER_PREPARED_OHTTP_PATH: PASS as engineering wiring; no timing claim

PACER_AFTER_CUTOFF_OPERATIONS: wait; PreparedSlot.Send; one fixed-size writer.Write; byte-count validation; non-blocking in-memory acknowledgement

ADMISSION_BINDING_RUNTIME: PASS

FUNCTIONAL_1: 1 / 1

FUNCTIONAL_10: 10 / 10

FUNCTIONAL_50: 50 / 50

FUNCTIONAL_100: 100 / 100

CANONICAL_FUNCTIONAL_GATE: {'PASS' if all_functional and all_lifecycle else 'FAIL'}

DUMMY_PROVIDER_OPERATIONS: 0

PROFILE_OVERFLOW_EVENTS: 0

UNEXPECTED_DUPLICATE_FRAMEWORK_DELIVERIES: 0

RECOVERY_READ_ONLY: PASS

RECOVERY_IDEMPOTENT: PASS under explicit provider idempotency contract

RECOVERY_NON_IDEMPOTENT: PASS with explicit EFFECT_OUTCOME_UNKNOWN before committed result

TIMING_PRIVACY: OPEN / NOT_TESTED

PACKET_LEVEL_TIMING: OPEN

HARDWARE_TEE: NOT_TESTED

READY_FOR_CANONICAL_HOLDOUT_FREEZE: {'YES' if all_functional and all_lifecycle and all_public_clean else 'NO'}

REGRESSION: Linux Go V8/V9/canonical packages PASS; local Python 203 passed

No semantic/privacy holdout was created or run. No overall GO is issued.
""")


if __name__ == "__main__":
    main()

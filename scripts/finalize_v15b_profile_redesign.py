from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_V15A = "6a04a67b6c54b8a01ca2a38a17247a486e420430"
GATEWAY_BYTES = 978_959
BYTES_PER_SLOT = 2_351_400
SELECTED_PUBLIC_SLOTS = 4
SELECTED_DELTA_MS = 350
INITIAL_LEAD_MS = 25


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position); high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def main() -> None:
    pipeline = json.loads((ROOT / "V15B_PIPELINE_SUMMARY.json").read_text())
    cadence = json.loads((ROOT / "V15B_CADENCE_STRESS_SUMMARY.json").read_text())
    full = json.loads((ROOT / "V15B_FULL_SESSION_RESULTS.json").read_text())
    structural = json.loads((ROOT / "V15B_STRUCTURAL_EQUIVALENCE.json").read_text())
    demand = list(csv.DictReader((ROOT / "V15B_AGENT_ACCESS_DEMAND.csv").open(newline="")))
    selected_demand = [row for row in demand if row["profile_selection_scope"] == "INCLUDED"]
    js = [float(row["agent_access_requests_J"]) for row in selected_demand]
    depths = [int(row["agent_access_causal_depth"]) for row in selected_demand]
    selected_cadence = cadence["candidates"][str(SELECTED_DELTA_MS)]
    if selected_cadence["slot_misses"] != 0 or selected_cadence["max_public_queue_depth"] != 0:
        raise RuntimeError("selected cadence did not close the fixed schedule")
    if not (
        full["full_session_schedule_pass"] and full["all_semantic_success"]
        and full["structural_equivalence"] and structural["exact_equality"]
    ):
        raise RuntimeError("full-session closure did not pass")

    profiles = [
        ("P1", 2, "ordinary single-Agent sessions"),
        ("P2", 4, "default V14 functional corpus, including two-level nested retrieval"),
        ("P3", 12, "higher-capacity option including historical six-level descriptor-transition demand"),
    ]
    costs = []
    pir = pipeline["pir_stage_ms"]
    for name, public_slots, purpose in profiles:
        agent_bytes = public_slots * BYTES_PER_SLOT
        costs.append({
            "profile": name,
            "R_A_public_slots": public_slots,
            "Delta_A_ms": SELECTED_DELTA_MS,
            "bootstrap_slots": 1,
            "drain_slots": 1,
            "total_agent_access_slots": public_slots,
            "public_horizon_ms": INITIAL_LEAD_MS + public_slots * SELECTED_DELTA_MS,
            "maximum_admitted_agent_requests": public_slots - 1,
            "guaranteed_serial_causal_depth": public_slots // 2,
            "psi_bytes_session": public_slots * 2_277_832,
            "pir_bytes_session": public_slots * 73_568,
            "agent_access_bytes_session": agent_bytes,
            "gateway_bytes_session": GATEWAY_BYTES,
            "total_public_bytes_session": agent_bytes + GATEWAY_BYTES,
            "total_public_mib_session": (agent_bytes + GATEWAY_BYTES) / 1_048_576,
            "median_admission_to_artifact_ready_ms": SELECTED_DELTA_MS + pir["p50"],
            "p95_admission_to_artifact_ready_ms": SELECTED_DELTA_MS + pir["p95"],
            "purpose": purpose,
        })
    with (ROOT / "V15B_PROFILE_COSTS.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(costs[0]))
        writer.writeheader(); writer.writerows(costs)

    candidate_lines = [
        "# V15B workload-driven Agent-access profile candidates", "",
        "All candidates use the same measured real wire cost (2,351,400 bytes per public PSI+PIR slot), the selected 350 ms conservative cadence, a dummy-PIR bootstrap in slot 0, and a final dummy-PSI drain. `R_A` is the total public slot count; maximum early-eligible request capacity is `R_A-1`.", "",
        "| Profile | R_A | Delta_A | Horizon | Max requests | Guaranteed serial depth | Agent-access bytes | Total with frozen Gateway | Intended scope |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in costs:
        candidate_lines.append(
            f"| {row['profile']} | {row['R_A_public_slots']} | {row['Delta_A_ms']} ms | "
            f"{row['public_horizon_ms']} ms | {row['maximum_admitted_agent_requests']} | "
            f"{row['guaranteed_serial_causal_depth']} | {row['agent_access_bytes_session']:,} B | "
            f"{row['total_public_bytes_session']:,} B ({row['total_public_mib_session']:.3f} MiB) | {row['purpose']} |"
        )
    candidate_lines += [
        "", "## Selection", "",
        "P2 is selected. The current paper-aligned V14 functional corpus has J=1 or 2 (median 1.5, p95/max 2) and maximum retrieval causal depth 2. P2 provides three admitted requests and guaranteed serial retrieval depth 2, leaving one request of non-causal headroom without paying for the historical 100-slot candidate. P1 cannot guarantee the nested path. P3 is retained only as an explicit high-capacity public option; selecting it would reveal that profile choice and would raise normalized traffic to 29,195,759 bytes/session.", "",
        "P2 still has a material cost: 9,405,600 Agent-access bytes and 10,384,559 total public bytes (9.903 MiB) per session. This is reported directly rather than compared to an arbitrary pass threshold. The redesign is accepted because the measured cryptographic cadence is sustainable, the selected profile covers the supported V14 workloads with explicit bounded capacity, and Agent-access traffic falls by 96.0% from the infeasible 100-slot projection. It is not evidence of timing indistinguishability.", "",
        "Overflow is fail-closed as `PROFILE_AGENT_ACCESS_CAPACITY_EXCEEDED`; the schedule never extends.",
    ]
    (ROOT / "V15B_PROFILE_CANDIDATES.md").write_text("\n".join(candidate_lines) + "\n")

    closure = {
        "schema": "AgentTool.V15BProfileRedesignClosure/1",
        "base_v15a_commit": BASE_V15A,
        "psi_backend": "Microsoft APSI v0.13.1",
        "psi_commit": "548745efdb37b1d7d948c761a772488747ca16ab",
        "pir_backend": "SimplePIR",
        "crypto_services_persistent": True,
        "per_slot_process_startup": False,
        "pipelined_psi_pir": "PASS",
        "pipeline_fixed_one_slot_offset": "PASS",
        "pipeline_benchmark": {
            "warm_slots": pipeline["warm_slots"], "slots_per_private_mix": pipeline["slots_per_mix"],
            "psi_stage_ms": pipeline["psi_stage_ms"], "pir_stage_ms": pipeline["pir_stage_ms"],
            "overlapped_slot_work_ms": pipeline["overlapped_slot_work_ms"],
            "wire_bytes_per_slot": pipeline["wire_bytes_per_slot"],
            "cold_first_query_after_services_ready_ms": pipeline["cold_slot_ms"],
            "simplepir_store_epoch_startup_ms": pipeline["services"]["simplepir_process_start_to_preprocessed_ready_ms"],
        },
        "cadence_stress": cadence,
        "maximum_tested_sustainable_slot_rate_per_second": 8.0,
        "maximum_tested_sustainable_rate_basis": "125-ms candidate completed 1000/1000 with zero misses; 100-ms candidate had 19 misses; not a future-host guarantee",
        "safe_delta_a_ms": SELECTED_DELTA_MS,
        "safe_delta_basis": "350-ms candidate completed 1000/1000 with zero deadline misses and zero backlog; maximum observed work was 217.598675 ms, leaving 132.401325 ms cadence margin",
        "workload_agent_access": {
            "selection_rows": len(selected_demand), "median": statistics.median(js),
            "p95": percentile(js, 0.95), "max": max(js), "max_causal_depth": max(depths),
            "historical_descriptor_k6_excluded_from_selection": True,
        },
        "selected_profile": {
            "profile": "P2", "R_A_public_slots": SELECTED_PUBLIC_SLOTS,
            "Delta_A_ms": SELECTED_DELTA_MS,
            "Agent_access_horizon_ms": INITIAL_LEAD_MS + SELECTED_PUBLIC_SLOTS * SELECTED_DELTA_MS,
            "maximum_admitted_agent_requests": SELECTED_PUBLIC_SLOTS - 1,
            "guaranteed_serial_causal_depth": SELECTED_PUBLIC_SLOTS // 2,
            "Agent_access_bytes_session": SELECTED_PUBLIC_SLOTS * BYTES_PER_SLOT,
            "Gateway_bytes_session": GATEWAY_BYTES,
            "total_public_bytes_session": SELECTED_PUBLIC_SLOTS * BYTES_PER_SLOT + GATEWAY_BYTES,
        },
        "full_session_schedule": "PASS",
        "structural_equivalence": "PASS",
        "full_session_harness_attempts": 2,
        "invalidated_harness_attempts": 1,
        "invalidated_harness_reason": "stateful one-shot ScriptedModel instance was reused across repeated semantic executions",
        "gateway_profile_changed": False,
        "new_privacy_attack_experiments": 0,
        "paper_files_modified": False,
        "v15b_decision": "PROFILE_REDESIGN_PASS",
    }
    (ROOT / "V15B_FINAL_CLOSURE.json").write_text(json.dumps(closure, indent=2) + "\n")
    md = f"""# V15B pipelined Agent-access profile redesign closure

## Decision

`V15B_DECISION = PROFILE_REDESIGN_PASS`.

Persistent real Microsoft APSI and SimplePIR services, combined with a fixed
one-stage public pipeline, reduce median complete slot work from the V15A
sequential 129.003 ms to {pipeline['overlapped_slot_work_ms']['p50']:.3f} ms.
The selected public profile is P2: `R_A=4`, `Delta_A=350 ms`, and a 1425 ms
Agent-access horizon including the 25 ms initial lead and completion envelope.
It admits at most three early-eligible requests and guarantees serial retrieval
depth two. Capacity overflow is explicit and fail-closed.

## Exact report

- `BASE_V15A_COMMIT`: `{BASE_V15A}`
- `PSI_BACKEND`: Microsoft APSI v0.13.1
- `PIR_BACKEND`: SimplePIR
- `CRYPTO_SERVICES_PERSISTENT`: YES
- `PER_SLOT_PROCESS_STARTUP`: NO
- `PIPELINED_PSI_PIR`: PASS
- `PIPELINE_FIXED_ONE_SLOT_OFFSET`: PASS
- `PSI_STAGE_P50`: {pipeline['psi_stage_ms']['p50']:.6f} ms
- `PSI_STAGE_P95`: {pipeline['psi_stage_ms']['p95']:.6f} ms
- `PSI_STAGE_P99`: {pipeline['psi_stage_ms']['p99']:.6f} ms
- `PIR_STAGE_P50`: {pipeline['pir_stage_ms']['p50']:.6f} ms
- `PIR_STAGE_P95`: {pipeline['pir_stage_ms']['p95']:.6f} ms
- `PIR_STAGE_P99`: {pipeline['pir_stage_ms']['p99']:.6f} ms
- `MAX_TESTED_SUSTAINABLE_SLOT_RATE`: 8.0 slots/s (125 ms; 1000/1000, not a future-host guarantee)
- `SAFE_DELTA_A`: 350 ms
- `WORKLOAD_AGENT_ACCESS_MEDIAN`: {statistics.median(js):g}
- `WORKLOAD_AGENT_ACCESS_P95`: {percentile(js, 0.95):g}
- `WORKLOAD_AGENT_ACCESS_MAX`: {max(js):g}
- `WORKLOAD_MAX_CAUSAL_DEPTH`: {max(depths)}
- `SELECTED_R_A`: 4 public slots
- `SELECTED_DELTA_A`: 350 ms
- `SELECTED_AGENT_ACCESS_HORIZON`: 1425 ms
- `SELECTED_PROFILE_BYTES_SESSION`: 10,384,559 total public bytes (9,405,600 Agent-access + 978,959 frozen Gateway)
- `SELECTED_PROFILE_MAX_AGENT_ACCESSES`: 3
- `FULL_SESSION_SCHEDULE`: PASS
- `STRUCTURAL_EQUIVALENCE`: PASS
- `GATEWAY_PROFILE_CHANGED`: NO
- `NEW_PRIVACY_ATTACK_EXPERIMENTS`: 0
- `PAPER_FILES_MODIFIED`: NO
- `V15B_DECISION`: PROFILE_REDESIGN_PASS

## Scope boundary

This closure establishes throughput feasibility and exact non-timing structural
equivalence for the selected public profile. It does not run or replace any
privacy classifier and does not establish realized timing indistinguishability.
"""
    (ROOT / "V15B_FINAL_CLOSURE.md").write_text(md)


if __name__ == "__main__":
    main()

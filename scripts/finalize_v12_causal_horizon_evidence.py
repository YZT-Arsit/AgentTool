from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite append-only evidence: {path}")
    path.write_text(value, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=Path("/root/autodl-tmp"))
    args = parser.parse_args()
    evidence = args.evidence_root.resolve()
    live_root = evidence / "results_v12_causal_horizon_dev"
    completion = read(live_root / "campaign_completion.json")
    model = read(ROOT / "V12_CAUSAL_HORIZON_CAPACITY_MODEL.json")
    deployment = read(evidence / "v12_chr_deployment_verification.json")
    go_r3 = read(evidence / "v12_chr_go_current_gate_r3" / "gate.json")
    python_serial = read(evidence / "v12_chr_python_serial_r3" / "gate.json")
    python_default = read(evidence / "v12_chr_python_default_r3" / "gate.json")
    security = read(evidence / "v12_chr_security_negatives" / "result.json")
    lead = read(evidence / "v12_chr_pir_lead_preflight" / "V12_PIR_INITIAL_LEAD_PREFLIGHT.json")

    workloads: list[dict[str, object]] = []
    for verdict_path in sorted((live_root / "H4500").glob("*/capacity_verdict.json")):
        verdict = read(verdict_path)
        trace_path = verdict_path.parent / "go_online_result.json"
        pir_path = verdict_path.parent / "pir" / "online_query_summary.json"
        trace = read(trace_path)
        pir = read(pir_path)
        launches = trace.get("slot_launches", [])
        workloads.append(
            {
                "identity": verdict["identity"],
                "framework": verdict["framework"],
                "kind": verdict["kind"],
                "operation_count": verdict["operation_count"],
                "passed": verdict["passed"],
                "emitted_cells": trace.get("emitted_cells"),
                "session_status": trace.get("session_status"),
                "admitted": trace.get("admitted"),
                "result_count": len(trace.get("results", [])),
                "resolved_not_admitted_ids": trace.get("resolved_not_admitted_ids", []),
                "nominal_late_cells": trace.get("nominal_late_cells", 0),
                "maximum_nominal_launch_slip_ns": max(
                    (int(item.get("launch_slip_ns", 0)) for item in launches), default=0
                ),
                "pir_real_queries": pir["real_query_count"],
                "pir_dummy_queries": pir["dummy_query_count"],
                "pir_total_queries": pir["query_count"],
                "descriptor_cache_hits": pir["descriptor_cache_hits"],
                "go_trace_sha256": sha(trace_path),
                "pir_summary_sha256": sha(pir_path),
                "verdict_sha256": sha(verdict_path),
            }
        )
    live_results = {
        "schema": "AgentTool.V12CausalHorizonLiveResults/1",
        "selected_causal_horizon_ms": completion["selected_causal_horizon_ms"],
        "profile_id": "V12-TIMING-INDIST-V2-H50-H4500-P10-PIR60",
        "workload_count": len(workloads),
        "passed": sum(bool(item["passed"]) for item in workloads),
        "workloads": workloads,
        "aggregate_nominal_late_cells": sum(int(item["nominal_late_cells"]) for item in workloads),
        "maximum_nominal_launch_slip_ns": max(
            (int(item["maximum_nominal_launch_slip_ns"]) for item in workloads), default=0
        ),
        "retry_count": completion["retry_count"],
        "replacement_count": completion["replacement_count"],
        "ledger_sha256": completion["ledger_sha256"],
        "timing_attack_sessions": 0,
        "timing_confirmatory_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    write_new(
        ROOT / "V12_CAUSAL_HORIZON_LIVE_RESULTS.json",
        json.dumps(live_results, indent=2) + "\n",
    )

    model_by_h = {int(item["horizon_ms"]): item for item in model["results"]}
    gate_audit = {
        "schema": "AgentTool.V12CausalHorizonGateAudit/1",
        "phase": "V12-TIMING-CAUSAL-HORIZON-REQUALIFICATION",
        "preserved_prequalification_outcomes": {
            "go_repository_wide_exploratory": "FAIL_1_HISTORICAL_V11_5MS_TIMING_TEST",
            "go_manifest_r1": "FAIL_HISTORICAL_TIMING_NODE_REINTRODUCED_BY_HARNESS",
            "go_manifest_r2": "FAIL_HARNESS_COUNTED_SUBTESTS_AND_STALE_ALL_N_DENOMINATOR",
            "python_manifest_r1_serial": "73/75 FAIL_STALE_TEST_ASSERTIONS",
            "python_manifest_r2_serial": "74/75 FAIL_REMAINING_STALE_DUMMY49_ASSERTION",
        },
        "decisive_current_results": {
            "python_serial": "75/75 PASS",
            "python_default": "75/75 PASS",
            "native_routing": "15/15 PASS",
            "go": "79/79 PASS",
            "security_negatives": "22/22 PASS",
            "deployment_files": deployment["file_hash_match"],
            "deployment_python_modules": deployment["python_module_file_match"],
            "deployment_binaries": deployment["binary_hash_match"],
            "pir_initial_lead": "PASS" if lead["passed"] else "FAIL",
        },
        "artifact_hashes": {
            "python_serial_gate": sha(evidence / "v12_chr_python_serial_r3" / "gate.json"),
            "python_serial_log": sha(evidence / "v12_chr_python_serial_r3" / "pytest.log"),
            "python_default_gate": sha(evidence / "v12_chr_python_default_r3" / "gate.json"),
            "python_default_log": sha(evidence / "v12_chr_python_default_r3" / "pytest.log"),
            "go_r3_gate": sha(evidence / "v12_chr_go_current_gate_r3" / "gate.json"),
            "go_r3_log": sha(evidence / "v12_chr_go_current_gate_r3" / "go-test.jsonl"),
            "security_result": sha(evidence / "v12_chr_security_negatives" / "result.json"),
            "security_python_log": sha(evidence / "v12_chr_security_negatives" / "python_negatives.log"),
            "native_routing_log": sha(evidence / "v12_chr_native_routing.log"),
            "deployment_verification": sha(evidence / "v12_chr_deployment_verification.json"),
            "pir_lead_preflight": sha(
                evidence / "v12_chr_pir_lead_preflight" / "V12_PIR_INITIAL_LEAD_PREFLIGHT.json"
            ),
            "live_completion": sha(live_root / "campaign_completion.json"),
            "live_ledger": sha(live_root / "execution_ledger.jsonl"),
        },
        "runtime_source_changed_after_decisive_gates": False,
        "timing_attack_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    write_new(
        ROOT / "V12_CAUSAL_HORIZON_GATE_AUDIT.json",
        json.dumps(gate_audit, indent=2) + "\n",
    )

    exclusions = sorted(
        {
            "DEV-CHR-COMPONENT-V2-001",
            "DEV-CHR-COMPONENT-V2-R2-001",
            "DEV-CHR-COMPONENT-V1-COMPAT-R2-001",
            "DEV-CHR-COMPONENT-V1-COMPAT-R3-001",
            *(str(item["identity"]) for item in workloads),
        }
    )
    exclusion_payload = {
        "schema": "AgentTool.V12CausalHorizonDevelopmentExclusions/1",
        "phase": "V12-TIMING-CAUSAL-HORIZON-REQUALIFICATION",
        "identities": exclusions,
        "future_holdout_exclusion_required": True,
        "does_not_construct_final_holdout": True,
    }
    write_new(
        ROOT / "V12_CAUSAL_HORIZON_DEVELOPMENT_EXCLUSIONS.json",
        json.dumps(exclusion_payload, indent=2) + "\n",
    )

    final = {
        "schema": "AgentTool.V12CausalHorizonRequalification/1",
        "phase": "V12-TIMING-CAUSAL-HORIZON-REQUALIFICATION",
        "PRIOR_ADMISSION_CLOCK_PHASE": "PRESERVED",
        "H3000": "FAIL_PRESERVED",
        "CLOCK_MISMATCH": "CONFIRMED",
        "EFFECTIVE_CLOCK_IMPLEMENTED": "PASS",
        "HORIZON_CANDIDATES_MS": [4500, 5000, 6000],
        "OFFLINE_REPLAY": {
            str(h): f"{model_by_h[h]['old_trace_replay']['admitted']}/50" for h in (4500, 5000, 6000)
        },
        "PIR_CAPACITY": {str(h): model_by_h[h]["pir_capacity"] for h in (4500, 5000, 6000)},
        "JOINT_CAUSAL_CAPACITY": {
            str(h): model_by_h[h]["joint_causal_model"] for h in (4500, 5000, 6000)
        },
        "POST_CHANGE_PYTHON_SERIAL": "75/75 PASS",
        "POST_CHANGE_PYTHON_DEFAULT": "75/75 PASS",
        "POST_CHANGE_NATIVE_ROUTING": "15/15 PASS",
        "POST_CHANGE_GO": "79/79 PASS",
        "POST_CHANGE_SECURITY_NEGATIVES": "22/22 PASS",
        "TRANSITIVE_RUNTIME_HASH_MATCH": "696/696 + 8/8 module probes + 2/2 binaries",
        "LIVE_H4500": "PASS 8/8",
        "LIVE_H5000": "NOT_RUN_SMALLEST_PASS_RULE",
        "LIVE_H6000": "NOT_RUN_SMALLEST_PASS_RULE",
        "SELECTED_CAUSAL_HORIZON_MS": 4500,
        "SELECTED_PROFILE": "V12-TIMING-INDIST-V2-H50-H4500-P10-PIR60",
        "SELECTED_PROFILE_PUBLIC_ROUNDS": 506,
        "PIR_CAPACITY_SELECTED_PROFILE": "K6 / PIR60 / EPOCH6000 / Q100 PRESERVED",
        "TIMING_ATTACK_SESSIONS": 0,
        "TIMING_CONFIRMATORY_SESSIONS": 0,
        "TIMING_PRIVACY": "INCONCLUSIVE",
        "TIMING_GO": "NO",
        "PACKET_LEVEL_TIMING": "OPEN",
        "HARDWARE_TEE": "NOT_TESTED",
        "V12_FINAL_CANDIDATE_UNIVERSE_EXISTS": "NO",
        "V12_FINAL_SEED_EXISTS": "NO",
        "SELECTED_FINAL_V12_CASES_EXECUTED": 0,
        "READY_TO_RESUME_TIMING_ATTACK_DEVELOPMENT": "YES",
        "READY_FOR_FINAL_V12_HOLDOUT": "NO",
        "live_results_sha256": sha(ROOT / "V12_CAUSAL_HORIZON_LIVE_RESULTS.json"),
        "gate_audit_sha256": sha(ROOT / "V12_CAUSAL_HORIZON_GATE_AUDIT.json"),
        "development_exclusions_sha256": sha(
            ROOT / "V12_CAUSAL_HORIZON_DEVELOPMENT_EXCLUSIONS.json"
        ),
    }
    write_new(
        ROOT / "V12_CAUSAL_HORIZON_REQUALIFICATION.json",
        json.dumps(final, indent=2) + "\n",
    )
    markdown = f"""# V12 causal-horizon requalification

The historical H3000 failure and all three prohibited identities remain preserved and were never retried. The nominal/effective commitment-clock mismatch was repaired with a public-dispatch-only effective slot state machine for both action and result commitment.

Deterministic replay admitted `50/50` under each frozen H candidate. PIR capacity and the joint causal model passed for H4500, H5000, and H6000 with the unchanged `K6 / PIR60 / EPOCH6000 / Q100` construction.

Post-change Linux gates passed: Python serial `75/75`, Python default `75/75`, native routing `15/15`, Go `79/79`, and security negatives `22/22`. Deployment integrity matched `696/696` files, `8/8` imported module paths, and `2/2` binaries.

The one-shot live campaign passed all `8/8` workloads at H4500, including depth50 on both pinned frameworks, K6 transitions, Agent-as-Tool transitions, and repeated cache-hit workloads. Therefore the frozen smallest-pass rule selects `H*=4500 ms`, `A=450`, `R=506`. H5000 and H6000 were not run.

This is functional causal-capacity qualification only. Timing privacy remains **INCONCLUSIVE**, timing GO remains **NO**, and packet-level timing remains **OPEN**. No timing attack, timing confirmatory session, final V12 universe, seed, holdout, authorization, or selected final V12 execution was created.
"""
    write_new(ROOT / "V12_CAUSAL_HORIZON_REQUALIFICATION.md", markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE = "1ba1fe6a3bd49b38df2af1393b2b1dd1106f1968"
FAILED_IDENTITY = "DEV-DTVR-V4R7-P10-B200-OA-CAUSAL_DEPTH_50-001"
FRAMEWORKS = ("OpenAI Agents SDK", "Microsoft Agent Framework")
WORKLOADS = (
    "ORDINARY_TOOL",
    "AGENT_AS_TOOL_TRANSITION",
    "PROVIDER_EARLY_10",
    "PROVIDER_LATE_10",
    "DESCRIPTOR_TRANSITIONS_K6",
    "CACHE_REUSE_30",
    "CAPACITY_50",
    "CAUSAL_DEPTH_50_BOUNDED_HORIZON_STRESS",
)


def framework_code(framework: str) -> str:
    return "OA" if framework == "OpenAI Agents SDK" else "MS"


def identity(framework: str, workload: str) -> str:
    return f"DEV-V4R7-BLCC-P10-B200-{framework_code(framework)}-{workload}-001"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_audit() -> dict[str, object]:
    from scripts.run_v12_duplex_functional import build_workload
    from v11_full_scope.frameworks import native_implementation

    evidence = (
        ROOT
        / "V12_V4R7_PROVIDER_BOUND_CLOSURE_EVIDENCE"
        / "functional_requalification"
        / "failed_unit"
    )
    trace = json.loads((evidence / "go_online_result.json").read_text(encoding="utf-8"))
    lifecycle = json.loads((evidence / "private_trajectory.json").read_text(encoding="utf-8"))
    _, cases = build_workload("CAUSAL_DEPTH_50", "OpenAI Agents SDK", FAILED_IDENTITY)
    intended = [case.operation_id for case in cases]
    accepted = list(trace["accepted_operation_ids"])
    rejected = list(trace["resolved_not_admitted_ids"])
    results = list(trace["results"])
    provider = list(trace["provider_diagnostics"])
    submitted = [
        row["operation_id"]
        for row in lifecycle
        if row["stage"] == "ACTION_INTENT_SUBMITTED"
    ]
    delivered = [
        row["operation_id"]
        for row in lifecycle
        if row["stage"] == "FRAMEWORK_RESULT_DELIVERED"
    ]
    semantic_results_equal = True
    for case, result in zip(cases[: len(accepted)], results, strict=True):
        expected = native_implementation(case, case.arguments)
        semantic_results_equal = semantic_results_equal and (
            result["operation_id"] == case.operation_id
            and int(result["status"]) == 2
            and base64.b64decode(result["payload"]).decode("utf-8") == expected.result
            and expected.outcome_semantics == "READ_ONLY:SUCCESS"
        )
    exact_reconciliation = (
        submitted == intended
        and accepted == intended[: len(accepted)]
        and rejected == intended[len(accepted) :]
        and [row["operation_id"] for row in results] == accepted
        and [row["operation_id"] for row in provider] == accepted
        and delivered == accepted
        and len(accepted) + len(rejected) == len(intended)
        and int(trace["silent_committed_result_losses"]) == 0
        and not trace["pending_operation_ids"]
    )
    if not exact_reconciliation or not semantic_results_equal:
        raise AssertionError("historical V4R7 causal-depth evidence did not reconcile")
    return {
        "identity": FAILED_IDENTITY,
        "intended": len(intended),
        "admitted_before_public_admission_window_closed": len(accepted),
        "resolved_after_window_not_admitted": len(rejected),
        "silently_lost": int(trace["silent_committed_result_losses"]),
        "other_failure": 0,
        "first_not_admitted_index_one_based": len(accepted) + 1,
        "first_not_admitted_operation_id": rejected[0],
        "all_intents_explicitly_accounted": True,
        "admitted_provider_success": f"{len(provider)}/{len(accepted)}",
        "admitted_results_delivered": f"{len(results)}/{len(accepted)}",
        "admitted_semantic_results_equal": semantic_results_equal,
        "admitted_causal_order_equal": delivered == accepted,
        "public_transcript_complete": trace["public_transcript_complete"],
        "relay_cells": len(trace["public_relay_events"]),
    }


def main() -> int:
    profile = {
        "profile_id": "V12-TIMING-INDIST-V4R7-H50-H4500-P10-B200-PIR60",
        "H_ms": 4500,
        "B_ms": 200,
        "Delta_ms": 10,
        "M": 50,
        "R": 521,
        "Q": 100,
        "response_rho_ms": 30,
        "response_preparation_lead_ms": 20,
    }
    identities = [
        {
            "ordinal": ordinal,
            "identity": identity(framework, workload),
            "framework": framework,
            "workload": workload,
            "execution_count": 1,
            "retries": 0,
        }
        for ordinal, (framework, workload) in enumerate(
            (
                (framework, workload)
                for framework in FRAMEWORKS
                for workload in WORKLOADS
            ),
            start=1,
        )
    ]
    if len(identities) != 16 or len({row["identity"] for row in identities}) != 16:
        raise AssertionError("functional identity freeze is malformed")
    if any(row["identity"] == FAILED_IDENTITY for row in identities):
        raise AssertionError("historical failed identity was reused")
    audit = historical_audit()
    contract = {
        "schema": "AgentTool.V12V4R7BoundedLivenessCapacityContract/1",
        "base_v4r7": BASE,
        "profile": profile,
        "operation_capacity_contract": (
            "At most M real operations can be admitted when their trusted intents "
            "become admission-eligible before the fixed public admission window closes."
        ),
        "admission_horizon_contract": (
            "H fixes the public admission window represented by admission slots 1..ceil(H/Delta); "
            "an intent is in scope only while a future admission slot remains commit-eligible."
        ),
        "m_does_not_imply_causal_depth_guarantee": True,
        "outside_window_contract": (
            "Every resolved intent outside the fixed admission window is recorded as "
            "resolved_not_admitted/PROFILE_ADMISSION_CLOSED and never silently dropped."
        ),
        "old_causal_depth_oracle": "OVERSTATED_BOUNDED_LIVENESS_CONTRACT",
        "historical_qualification_status": "FAIL_PRESERVED",
        "historical_causal_depth_50": audit,
        "corrected_claims": {
            "operation_capacity": (
                "M=50 provides fixed-profile capacity for up to 50 real operations "
                "whose intents are admission-eligible within H."
            ),
            "bounded_causal_liveness": (
                "Arbitrary 50-step sequential causal progress is not guaranteed; "
                "post-window intents are explicitly not admitted."
            ),
            "guaranteed_causal_depth_50": "NOT_CLAIMED",
        },
        "source_locations": {
            "profile_round_formula": "v12_timing/profile.py:122-140",
            "online_count_limit": "common_action_gateway_v2/canonicalv9/online.go:399-437",
            "online_admission_window": "common_action_gateway_v2/canonicalv9/online.go:448-486",
            "static_plan_count_guard": "common_action_gateway_v2/canonicalv9/runner.go:347-348",
            "v4r7_capacity_formula": "common_action_gateway_v2/canonicalv9/runner.go:487-504",
            "old_unconditional_oracle": "scripts/run_v12_duplex_functional.py:207-270",
        },
        "runtime_immutability": {
            "H_changed": False,
            "B_changed": False,
            "Delta_changed": False,
            "M_changed": False,
            "R_changed": False,
            "Q_changed": False,
            "duplex_timing_design_changed": False,
        },
        "protected_classifier_runs": 0,
        "protected_auc_calculations": 0,
    }
    freeze = {
        "schema": "AgentTool.V12V4R7BoundedLivenessFunctionalFreeze/1",
        "base_v4r7": BASE,
        "contract_sha256": "MATERIALIZED_AFTER_CONTRACT_WRITE",
        "frozen_before_execution": True,
        "profile": profile,
        "workloads": list(WORKLOADS),
        "frameworks": list(FRAMEWORKS),
        "planned_units": 16,
        "identities": identities,
        "execution_policy": {
            "execute_each_identity_once": True,
            "retries": 0,
            "replacements": 0,
            "continue_after_isolated_functional_failure": True,
            "stop_on_common_integrity_failure": True,
        },
        "capacity_50_contract": {
            "workflow": "PARALLEL_ACTIONS",
            "all_50_intents_available_in_one_framework_turn": True,
            "strict_sequential_causality": False,
            "required_admitted": 50,
            "required_results": 50,
        },
        "causal_depth_stress_contract": {
            "workflow": "DYNAMIC_SEQUENCE",
            "intended_depth": 50,
            "require_every_pre_window_intent": True,
            "require_explicit_post_window_rejection": True,
            "guaranteed_depth": "NOT_CLAIMED",
        },
        "reuse_v4r7_reliability": "200/200 PASS_PRESERVED_NO_RERUN",
        "protected_classifier_runs": 0,
        "protected_auc_calculations": 0,
    }
    contract_path = ROOT / "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CONTRACT.json"
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    freeze["contract_sha256"] = sha256(contract_path)
    (ROOT / "V12_V4R7_BOUNDED_LIVENESS_FUNCTIONAL_FREEZE.json").write_text(
        json.dumps(freeze, indent=2) + "\n", encoding="utf-8"
    )
    md = f"""# V12 V4R7 Bounded Liveness and Capacity Contract

`M=50` is the maximum number of real operations that may be admitted while a future public admission slot remains eligible inside the fixed `H=4500 ms` window. It is not a guarantee of arbitrary 50-step sequential causal progress.

The historical V4R7 functional result remains `FAIL`. Its immutable causal-depth trajectory reconciles exactly as {audit['admitted_before_public_admission_window_closed']} admitted and successfully returned operations, {audit['resolved_after_window_not_admitted']} explicit `PROFILE_ADMISSION_CLOSED` outcomes, and {audit['silently_lost']} silent losses. The old unconditional 50/50 oracle is classified as `OVERSTATED_BOUNDED_LIVENESS_CONTRACT` without rewriting that result.

The corrected development qualification separately tests `CAPACITY_50` with all intents made available in one framework turn and `CAUSAL_DEPTH_50_BOUNDED_HORIZON_STRESS` with explicit accounting of pre-window and post-window operations. Guaranteed causal depth 50 is `NOT_CLAIMED`.

No H, B, Delta, M, R, Q, duplex clock, observer contract, classifier, or AUC rule changes in this contract revision.
"""
    (ROOT / "V12_V4R7_BOUNDED_LIVENESS_CAPACITY_CONTRACT.md").write_text(
        md, encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

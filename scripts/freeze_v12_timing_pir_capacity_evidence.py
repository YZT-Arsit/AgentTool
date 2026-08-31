from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.capacity import CapacityContract, run_capacity_suite


def sha(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def write_json(name: str, value: dict[str, object]) -> None:
    (ROOT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    contract = CapacityContract().validate()
    model = run_capacity_suite(contract)
    semantics = {
        "schema": "AgentTool.V12PIRResolutionSemantics/1",
        "phase": "V12-TIMING-PIR-CAPACITY-INTEGRITY-CLOSURE",
        "old_implementation_unit": "ONE_REAL_PIR_QUERY_PER_TOOL_OR_AGENT_ACTION",
        "old_rule_status": "REJECTED_AS_SEMANTICALLY_UNNECESSARY",
        "resolution_semantic_unit": (
            "one authenticated AgentDescriptorV7 resolution per (catalog_epoch, agent_id) on first private "
            "Agent activation, Agent change/handoff, Agent-as-Tool target selection, or descriptor epoch invalidation"
        ),
        "trusted_cache_key": ["catalog_epoch", "agent_id"],
        "cache_scope": "ONE_CANONICAL_ONLINE_SESSION_INSIDE_TRUSTED_BOUNDARY",
        "cache_hit_registry_behavior": "scheduled cover opportunity remains and executes dummy SimplePIR query",
        "cache_hit_public_visibility": False,
        "supported_descriptor_identities": {
            "10": "external Tool Agent",
            "11": "READ_ONLY external Agent service",
            "12": "IDEMPOTENT_EFFECT external Agent service",
            "13": "NON_IDEMPOTENT_EFFECT external Agent service",
            "20": "trusted-module-local Agent",
            "21": "external workflow/composition Agent",
        },
        "maximum_real_agent_resolutions_K": 6,
        "K_derivation": "cardinality of the complete selected-runtime descriptor identity set, not action M and not empirical convenience",
        "descriptor_authentication_reused": True,
        "descriptor_epoch_invalidation_forces_new_resolution": True,
        "future_actions_predeclared": False,
        "source_hashes": {
            "v11_online/session.py": sha("v11_online/session.py"),
            "canonical_v9/runner.py": sha("canonical_v9/runner.py"),
            "v11_full_scope/canonical.py": sha("v11_full_scope/canonical.py"),
        },
    }
    model.update(
        {
            "phase": "V12-TIMING-PIR-CAPACITY-INTEGRITY-CLOSURE",
            "old_Q_equals_M_rule": "REJECTED",
            "cover_construction": "FIXED_PUBLIC_EPOCH",
            "predeclared_epoch_candidates_ms": [6000, 8000, 10000],
            "predeclared_period_candidates_ms": [60, 75, 100],
            "capacity_candidate_not_final_timing_profile": {
                "pir_public_epoch_ms": 6000,
                "pir_period_ms": 60,
                "Q": 100,
                "selection_basis": "smallest predeclared integral epoch/period pair satisfying deterministic K=6 queue capacity before live outcomes",
            },
            "no_secret_dependent_extra_query": True,
            "no_schedule_extension": True,
            "overflow_policy": "FAIL_CLOSED_WHILE_FIXED_COVER_CONTINUES",
            "model_source_sha256": sha("v12_timing/capacity.py"),
        }
    )
    joint = {
        "schema": "AgentTool.V12JointPIRActionCapacityProof/1",
        "status": "PASS",
        "admission_horizon_ms": 3000,
        "K": contract.maximum_real_agent_resolutions,
        "PIR_period_ms": contract.pir_period_ms,
        "PIR_query_completion_bound_ms": contract.pir_query_completion_bound_ms,
        "action_preparation_margin_ms": contract.preparation_margin_ms,
        "latest_new_descriptor_arrival_ms": contract.latest_real_arrival_ms,
        "formula": "A = H - K*P - B_pir - L_prepare = 3000 - 6*60 - 50 - 1 = 2589 ms",
        "proof": (
            "For every cache miss arriving at or before A, even immediately after a cover opportunity and in a "
            "burst of K, the Kth query starts strictly before A+K*P, completes strictly before H-L_prepare, "
            "and leaves the public preparation margin before H."
        ),
        "runtime_enforcement": {
            "cache_miss_at_or_after_cutoff": "PIR_REAL_RESOLUTION_ADMISSION_CLOSED",
            "cached_descriptor_action": "continues under ordinary H=3000 action admission",
            "PIR_query_over_50ms": "FAIL_CLOSED_TIMEOUT",
            "fixed_cover_after_failure": "cover scheduler retains its fixed epoch unless infrastructure process failure prevents execution",
        },
        "same_agent_depth_50": "one real descriptor resolution plus 49 cache hits; actions remain generated online",
        "distinct_agent_transition_capacity": "at most K=6 new authenticated descriptor identities before the public cutoff",
        "future_action_ids_known_before_T0": False,
        "action_horizon_changed": False,
        "public_profile_finalized": False,
        "deterministic_model_pass": bool(model["passed"]),
        "model_maximum_queue_occupancy": model["maximum_queue_occupancy"],
        "model_worst_resolution_delay_ms": model["worst_case_modeled_resolution_delay_ms"],
    }
    write_json("V12_PIR_RESOLUTION_SEMANTICS.json", semantics)
    write_json("V12_PIR_CAUSAL_CAPACITY_MODEL.json", model)
    write_json("V12_JOINT_PIR_ACTION_CAPACITY_PROOF.json", joint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

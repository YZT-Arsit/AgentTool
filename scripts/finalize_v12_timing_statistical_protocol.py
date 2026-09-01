from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BASE = "d3a042aae00033ad2b0cf81b2571b7c428405685"
PHASE = "V12-TIMING-STATISTICAL-PROTOCOL-AND-LOCAL-CONTROL-CLOSURE"
RUNTIME_PATHS = (
    "common_action_gateway_v2/canonicalv9/runner.go",
    "common_action_gateway_v2/v8/http_relay.go",
    "pir_integration/simplepir_bridge/main.go",
    "v11_online/session.py",
    "v12_timing/profile.py",
)


def _read_json(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _write_new(name: str, value: str) -> None:
    path = ROOT / name
    if path.exists():
        raise SystemExit(f"refusing to overwrite append-only evidence: {path}")
    path.write_text(value, encoding="utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def main() -> int:
    if _git("rev-parse", "HEAD").decode().strip() != BASE:
        raise SystemExit("phase finalization must begin at the exact functional base commit")
    calibration = _read_json("V12_TIMING_NULL_PRECISION_CALIBRATION.json")
    controls = _read_json("V12_TIMING_SYNTHETIC_PIPELINE_CONTROL.json")
    functional = _read_json("V12_APPLICATION_OBSERVABILITY_AND_DELTA_FUNCTIONAL_QUALIFICATION.json")
    if calibration["selected_eval_blocks"] != 600 or controls["status"] != "PASS":
        raise SystemExit("calibration/control evidence does not satisfy closure prerequisites")
    if any(functional["profiles"][key]["status"] != "FUNCTIONALLY_ELIGIBLE" for key in ("10", "20", "25")):
        raise SystemExit("functional eligibility was not preserved")

    runtime_hashes: dict[str, dict[str, object]] = {}
    for relative in RUNTIME_PATHS:
        base_bytes = _git("show", f"{BASE}:{relative}")
        base_blob = _git("rev-parse", f"{BASE}:{relative}").decode().strip()
        current_blob = _git("hash-object", "--", relative).decode().strip()
        runtime_hashes[relative] = {
            "base_git_blob": base_blob,
            "current_git_blob": current_blob,
            "normalized_content_sha256": _sha256(base_bytes),
            "match": base_blob == current_blob,
        }
    if not all(row["match"] for row in runtime_hashes.values()):
        raise SystemExit("protected runtime immutability check failed")

    prior_functional = _read_json("V12_APPLICATION_OBSERVABILITY_DEVELOPMENT_EXCLUSIONS.json")["identities"]
    prior_methodology = _read_json("V12_TIMING_DEVELOPMENT_EXCLUSIONS.json")["excluded_observed_identities"]
    methodology_identities = [
        "METH-V2-UNIT-TRAIN-SELECTION",
        "METH-V2-UNIT-COMPLETE-BLOCK-INFERENCE",
        "METH-V2-NULL-PRECISION-PLANNING",
    ]
    synthetic_identities = [
        f"LOCAL-SYNTH-P25-{observer}-B{block:04d}-C{label}"
        for observer in ("RELAY", "REGISTRY")
        for block in range(250)
        for label in (0, 1)
    ]
    exclusions = {
        "schema": "AgentTool.V12TimingDevelopmentExclusionsV2/1",
        "phase": PHASE,
        "prior_functional_identities": prior_functional,
        "prior_methodology_identities": prior_methodology,
        "current_methodology_test_identities": methodology_identities,
        "local_synthetic_control_identities": synthetic_identities,
        "counts": {
            "prior_functional": len(prior_functional),
            "prior_methodology": len(prior_methodology),
            "current_methodology": len(methodology_identities),
            "local_synthetic_control": len(synthetic_identities),
            "total": len(prior_functional) + len(prior_methodology) + len(methodology_identities) + len(synthetic_identities),
        },
        "future_fresh_timing_confirmation_exclusion_required": True,
        "constructs_confirmatory_or_final_universe": False,
    }
    _write_new("V12_TIMING_DEVELOPMENT_EXCLUSIONS_V2.json", json.dumps(exclusions, indent=2) + "\n")

    protocol = {
        "schema": "AgentTool.V12TimingStatisticalProtocolV2/1",
        "phase": PHASE,
        "base_functional_commit": BASE,
        "frozen_methodology_results": {
            "old_16_row_primary_nonlinear_validity": "FAIL_PRESERVED",
            "old_matrix_disposition": "AUXILIARY_FACTORIAL_ONLY",
            "t1_isolated_primary": "NOT_FEASIBLE",
            "observers": ["REGISTRY_APPLICATION_OPERATOR", "RELAY_APPLICATION_OPERATOR"],
            "view": "TIMING_ONLY_VIEW",
            "complete_application_timing_view": "PASS",
        },
        "historical_eval_family_max": "PRESERVED_BUT_SUPERSEDED_FOR_DECISIVE_USE",
        "protocol_revision": "TRAIN_SELECTED_CLASSIFIER_V2",
        "development_seed": {
            "label": "V12-TIMING-TRAIN-SELECTED-V2-20260831",
            "coordinate_derivation": "first 64 bits of SHA256(label|profile|task|framework|observer)",
            "is_final_v12_seed": False,
        },
        "coordinate": ["profile", "task", "framework", "observer"],
        "block": "one class-0 session plus one class-1 session",
        "split": {"train_percent": 60, "eval_percent": 40, "unit": "COMPLETE_MATCHED_BLOCK"},
        "candidate_models": ["LOGISTIC_REGRESSION", "EXTRA_TREES", "HIST_GRADIENT_BOOSTING", "RBF_SVM"],
        "model_definitions": {
            "LOGISTIC_REGRESSION": {"preprocessing": "StandardScaler fit on applicable TRAIN fold or all TRAIN only", "hyperparameters": {"C": 1.0, "max_iter": 2000}},
            "EXTRA_TREES": {"preprocessing": "NONE", "hyperparameters": {"n_estimators": 300, "min_samples_leaf": 3, "max_features": "sqrt", "n_jobs": 1}},
            "HIST_GRADIENT_BOOSTING": {"preprocessing": "NONE", "hyperparameters": {"learning_rate": 0.08, "max_iter": 200, "max_leaf_nodes": 15, "l2_regularization": 1.0}},
            "RBF_SVM": {"preprocessing": "StandardScaler fit on applicable TRAIN fold or all TRAIN only", "hyperparameters": {"C": 1.0, "gamma": "scale", "kernel": "rbf", "probability": True}},
        },
        "tie_break_order": ["LOGISTIC_REGRESSION", "EXTRA_TREES", "HIST_GRADIENT_BOOSTING", "RBF_SVM"],
        "selection": {
            "data": "DEVELOPMENT_TRAIN_ONLY",
            "cross_validation": "DETERMINISTIC_GROUPED_BLOCK_RESPECTING_5_FOLD",
            "orientation": "NORMAL if TRAIN-CV AUC >= 0.5 else INVERTED",
            "ranking": "max(TRAIN_CV_AUC, 1-TRAIN_CV_AUC)",
            "selected_model_count": 1,
            "preprocessing_fit": "TRAIN_ONLY",
            "final_fit": "ALL_TRAIN_BLOCKS_ONLY",
        },
        "evaluation": {
            "statistic": "SELECTED_MODEL_EVAL_AUC",
            "fixed_prediction_vectors": 1,
            "post_hoc_eval_orientation": False,
            "other_models_eval_used_for_verdict": False,
        },
        "bootstrap": {
            "population": "DEVELOPMENT_EVAL_ONLY",
            "unit": "COMPLETE_MATCHED_EVAL_BLOCK",
            "resamples": 10000,
            "refit": False,
            "reselect_model": False,
            "reselect_orientation": False,
            "protected_ucb95_rule": "95th percentile <= 0.55",
            "control_lcb95_rule": "5th percentile >= 0.60",
            "secondary_two_sided_ci": "2.5th and 97.5th percentiles",
        },
        "randomization": {
            "operation": "independently swap labels within complete matched EVAL blocks",
            "role": "SECONDARY_NULL_CONSISTENCY_DIAGNOSTIC_ONLY",
        },
        "tasks": {
            "primary_isolated": ["T2", "T3", "T4", "T5", "T6", "T9"],
            "primary_composite": ["T7", "T8", "T10"],
            "t1": "NOT_FEASIBLE_AS_ISOLATED_PRIMARY",
            "auxiliary_registry_composite": "C1_REGISTRY_RESOLUTION_PATTERN",
            "c1_claim_limit": "end-to-end Registry timing comparison only; no one-factor causal attribution",
        },
        "frameworks": ["OpenAI Agents SDK", "Microsoft Agent Framework"],
        "observer_reuse": "one generated session may provide both applicable observer projections",
        "profile_order": ["P10", "P20", "P25"],
        "sentinel": {
            "comparisons": ["C1_REGISTRY_RESOLUTION_PATTERN", "T4", "T7", "T9"],
            "train_blocks": 75,
            "eval_blocks": 50,
            "total_blocks": 125,
            "sessions_per_coordinate": 250,
            "independent_from_full_dataset": True,
            "only_outcome": "EARLY_STATISTICAL_FAIL when one-sided LCB95 > 0.55",
            "privacy_pass_allowed": False,
            "model_feature_task_changes_allowed": False,
        },
        "runtime_immutability": {"status": "PASS", "files": runtime_hashes},
        "protected_execution_in_this_phase": {
            "P10_sessions": 0,
            "P20_sessions": 0,
            "P25_sessions": 0,
            "protected_classifier_training_runs": 0,
            "protected_real_auc_calculations": 0,
        },
    }
    _write_new("V12_TIMING_STATISTICAL_PROTOCOL_V2.json", json.dumps(protocol, indent=2) + "\n")

    local_audit = {
        "schema": "AgentTool.V12TimingLocalControlAudit/1",
        "phase": PHASE,
        "live_relay_control": {
            "status": "NOT_FEASIBLE",
            "reason": "existing B2 unshaped microbenchmark uses the requested real-operation count and content-dependent request/response buckets; it is not a fixed-R complete Relay observer sequence",
            "evidence": [
                "common_action_gateway_v2/cmd/v12-baseline-bench/main.go:26-36",
                "common_action_gateway_v2/cmd/v12-baseline-bench/main.go:141-178",
            ],
            "protected_runtime_modified": False,
            "executed": False,
        },
        "live_registry_control": {
            "status": "NOT_FEASIBLE",
            "reason": "the owned online Registry path fixes opportunities to epoch/period; no existing no-cover mode preserves fixed Q=100 while producing the requested live contrast",
            "evidence": ["v11_online/session.py:289-332", "v12_timing/profile.py:90-91"],
            "variable_query_count_control": "STRUCTURAL_METADATA_CONTROL_ONLY",
            "protected_runtime_modified": False,
            "executed": False,
        },
        "synthetic_pipeline_control": {
            "status": controls["status"],
            "fixed_dimensions": True,
            "result_file": "V12_TIMING_SYNTHETIC_PIPELINE_CONTROL.json",
        },
    }
    _write_new("V12_TIMING_LOCAL_CONTROL_AUDIT.json", json.dumps(local_audit, indent=2) + "\n")

    closure = {
        "schema": "AgentTool.V12TimingStatisticalProtocolAndLocalControlClosure/1",
        "phase": PHASE,
        "base_functional_commit": BASE,
        "frozen_methodology_results": {
            "old_16_row_primary_nonlinear_validity": "FAIL_PRESERVED",
            "old_matrix_disposition": "AUXILIARY_FACTORIAL_ONLY",
            "t1_isolated_primary": "NOT_FEASIBLE",
            "observers": ["REGISTRY_APPLICATION_OPERATOR", "RELAY_APPLICATION_OPERATOR"],
            "view": "TIMING_ONLY_VIEW",
            "complete_application_timing_view": "PASS",
        },
        "functional_eligibility": {"P10": "ELIGIBLE_PRESERVED", "P20": "ELIGIBLE_PRESERVED", "P25": "ELIGIBLE_PRESERVED"},
        "prior_software_evidence_preserved": {
            "python_serial": "100/100", "python_default": "100/100", "native_routing": "15/15",
            "go": "83/83", "security_negatives": "22/22",
            "deployment": "691/691 files + 8/8 module probes + 2/2 binaries",
        },
        "train_only_model_selection": "PASS",
        "train_only_score_orientation": "PASS",
        "decisive_eval_model_count": 1,
        "matched_eval_block_bootstrap": "PASS",
        "protected_one_sided_ucb_rule": "UCB95 <= 0.55",
        "control_one_sided_lcb_rule": "LCB95 >= 0.60",
        "null_precision_calibration": "PASS",
        "selected_eval_blocks": 600,
        "selected_train_blocks": 900,
        "total_blocks_per_coordinate": 1500,
        "estimated_protected_session_cost": calibration["protected_execution_cost"],
        "resource_limit_before_protected_evaluation": "NOT_DECLARED; operational review required for the frozen cost",
        "synthetic_timing_pipeline_control": controls["status"],
        "live_relay_control": "NOT_FEASIBLE",
        "live_registry_control": "NOT_FEASIBLE",
        "primary_isolated_tasks": ["T2", "T3", "T4", "T5", "T6", "T9"],
        "primary_composite_tasks": ["T7", "T8", "T10"],
        "auxiliary_registry_composite": "C1_REGISTRY_RESOLUTION_PATTERN",
        "development_exclusions": "V12_TIMING_DEVELOPMENT_EXCLUSIONS_V2.json",
        "runtime_immutability": "PASS",
        "prohibited_execution": {
            "protected_classifier_training_runs": 0,
            "protected_real_auc_calculations": 0,
            "selected_timing_delta_ms": "NONE",
            "timing_confirmatory_sessions": 0,
            "final_b4_b5": "NOT_RUN",
            "final_candidate_universe_exists": "NO",
            "final_seed_exists": "NO",
            "selected_final_v12_cases_executed": 0,
        },
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
        "ready_for_protected_timing_development": "YES",
        "ready_for_timing_confirmatory": "NO",
        "ready_for_final_v12_holdout": "NO",
    }
    _write_new("V12_TIMING_STATISTICAL_PROTOCOL_AND_LOCAL_CONTROL_CLOSURE.json", json.dumps(closure, indent=2) + "\n")

    protocol_md = f"""# V12 timing statistical protocol V2

Base functional commit: `{BASE}`. This revision preserves the historical EVAL-side four-model maximum as prior methodology evidence but supersedes it for all decisive future use.

For each profile/task/framework/observer coordinate, complete matched blocks are split 60% TRAIN and 40% EVAL. Five-fold grouped cross-validation on TRAIN alone ranks the four frozen model families by `max(TRAIN-CV AUC, 1 - TRAIN-CV AUC)`. Score orientation is frozen from TRAIN (`NORMAL` at AUC >= 0.5, otherwise `INVERTED`), with model-name order as the deterministic tie break. The selected model and its preprocessing are then fitted on all TRAIN blocks. Exactly one fixed, TRAIN-oriented score vector is generated on EVAL.

Development split/CV/model seeds are coordinate-specific and derived as the first 64 bits of `SHA256("V12-TIMING-TRAIN-SELECTED-V2-20260831" | profile | task | framework | observer)`. This is a development protocol seed label, not a final V12 holdout seed.

The decisive statistic is the selected model's raw EVAL AUC after applying the TRAIN-frozen orientation. There is no EVAL-side model selection and no `max(EVAL AUC, 1-EVAL AUC)`. EVAL uncertainty uses 10,000 complete matched-block bootstrap resamples without refitting or reselection. Protected development requires the 95th percentile UCB to be at most 0.55. A local control requires the 5th percentile LCB to be at least 0.60. A two-sided 95% interval and within-pair label-randomization p-value are secondary diagnostics.

The frozen full denominator is 900 TRAIN + 600 EVAL = 1,500 blocks per coordinate, or 3,000 sessions. With ten workload comparisons per framework and two frameworks, this is 60,000 sessions per profile. Since every candidate's public schedule floor is 6,000 ms, the serial floor is 100 hours per profile; all three candidates would be 180,000 sessions and 300 hours (12.5 days), excluding startup, analysis, and queueing.

The optional sentinel is independent from the full dataset: 75 TRAIN + 50 EVAL blocks for C1, T4, T7, and T9 in each framework. It can only return `EARLY_STATISTICAL_FAIL` when the one-sided LCB95 is above 0.55; it cannot support a privacy pass or change models, features, tasks, or the frozen full denominator.

No protected trace was read, no protected classifier was trained, and no protected AUC was calculated in this phase.
"""
    _write_new("V12_TIMING_STATISTICAL_PROTOCOL_V2.md", protocol_md)

    audit_md = """# V12 local timing-control audit

`LIVE_RELAY_CONTROL = NOT_FEASIBLE`. The existing owned B2 unshaped benchmark is a variable-operation-count microbenchmark and uses content-dependent request and response buckets. It is not a fixed-R complete Relay application-operator sequence. Creating a qualifying mode would require new runtime behavior, which this phase forbids.

`LIVE_REGISTRY_CONTROL = NOT_FEASIBLE`. The existing online Registry path binds opportunities to the public epoch/period recurrence. No existing no-cover path preserves fixed Q=100 while producing the requested live contrast. A one-query versus six-query comparison remains structural metadata only and cannot validate fixed-Q timing-only inference.

The fixed-dimension local synthetic controls are the permitted sensitivity controls. Both Relay (R=233) and Registry (Q=100) passed the TRAIN-selection, single-EVAL-model, and complete-block-bootstrap pipeline with LCB95=1.0. No live control was executed.
"""
    _write_new("V12_TIMING_LOCAL_CONTROL_AUDIT.md", audit_md)

    closure_md = f"""# V12 timing statistical protocol and local-control closure

The TRAIN-selected-classifier V2 protocol and fixed-dimension synthetic sensitivity controls pass. P10, P20, and P25 remain functionally eligible; no Delta is selected and timing privacy remains inconclusive.

## Required closure fields

```text
BASE_FUNCTIONAL_COMMIT: {BASE}
P10_FUNCTIONAL: ELIGIBLE_PRESERVED
P20_FUNCTIONAL: ELIGIBLE_PRESERVED
P25_FUNCTIONAL: ELIGIBLE_PRESERVED
TRAIN_ONLY_MODEL_SELECTION: PASS
TRAIN_ONLY_SCORE_ORIENTATION: PASS
DECISIVE_EVAL_MODEL_COUNT: 1
MATCHED_EVAL_BLOCK_BOOTSTRAP: PASS
PROTECTED_ONE_SIDED_UCB_RULE: UCB95 <= 0.55
CONTROL_ONE_SIDED_LCB_RULE: LCB95 >= 0.60
NULL_PRECISION_CALIBRATION: PASS
SELECTED_EVAL_BLOCKS: 600
SELECTED_TRAIN_BLOCKS: 900
TOTAL_BLOCKS_PER_COORDINATE: 1500
ESTIMATED_PROTECTED_SESSION_COST: 3,000 sessions/coordinate; 60,000 sessions and 100 serial public-schedule hours/profile; 180,000 sessions and 300 hours (12.5 days) worst-case across P10/P20/P25; excludes startup, analysis, and queueing
SYNTHETIC_TIMING_PIPELINE_CONTROL: PASS
LIVE_RELAY_CONTROL: NOT_FEASIBLE
LIVE_REGISTRY_CONTROL: NOT_FEASIBLE
PRIMARY_ISOLATED_TASKS: T2,T3,T4,T5,T6,T9
PRIMARY_COMPOSITE_TASKS: T7,T8,T10
AUXILIARY_REGISTRY_COMPOSITE: C1_REGISTRY_RESOLUTION_PATTERN
PROTECTED_CLASSIFIER_TRAINING_RUNS: 0
PROTECTED_REAL_AUC_CALCULATIONS: 0
SELECTED_TIMING_DELTA_MS: NONE
TIMING_PRIVACY: INCONCLUSIVE
TIMING_GO: NO
TIMING_CONFIRMATORY_SESSIONS: 0
FINAL_B4_B5: NOT_RUN
V12_FINAL_CANDIDATE_UNIVERSE_EXISTS: NO
V12_FINAL_SEED_EXISTS: NO
SELECTED_FINAL_V12_CASES_EXECUTED: 0
READY_FOR_PROTECTED_TIMING_DEVELOPMENT: YES
READY_FOR_TIMING_CONFIRMATORY: NO
READY_FOR_FINAL_V12_HOLDOUT: NO
```
"""
    _write_new("V12_TIMING_STATISTICAL_PROTOCOL_AND_LOCAL_CONTROL_CLOSURE.md", closure_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

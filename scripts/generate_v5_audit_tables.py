from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> list[dict[str, str]]:
    with (ROOT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write(name: str, rows: list[dict[str, object]]) -> None:
    path = ROOT / name
    if path.exists():
        raise FileExistsError(f"refusing to overwrite V5 artifact: {path}")
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main() -> None:
    workflow = []
    for row in read("WHOLE_WORKFLOW_EXECUTABLE_COVERAGE_V2.csv"):
        workflow.append({
            **row, "v5_status": row["status"],
            "v5_promotion": "NO",
            "v5_reason": "no new source-file workflow promoted without fresh source-traceable semantic confirmation",
        })
    write("WHOLE_WORKFLOW_COVERAGE_V5.csv", workflow)

    mapping = {
        "SOURCE_TRACEABLE_BOUNDED": "BOUNDED_AFTER_NORMALIZATION",
        "FRAMEWORK_CONTRACT_BOUNDED": "BOUNDED_UNDER_EXPLICIT_FRAMEWORK_CONTRACT",
        "EXTRACTOR_AMBIGUOUS": "EXTRACTOR_AMBIGUITY",
    }
    mixed = []
    for row in read("MIXED_UNPROVEN_DECOMPOSITION_V2.csv"):
        old = row["mixed_subclass"]
        if old in mapping:
            new = mapping[old]
        elif row["behavior_kind"] == "dynamic_instructions":
            new = "GENUINELY_ARBITRARY_PYTHON_RUNTIME"
        else:
            new = "CONTROL_RELEVANT_DYNAMIC_BEHAVIOR"
        mixed.append({
            **row, "v5_subclass": new,
            "data_only_semantics": "NO_ESTABLISHED_INSTANCE" if new != "DATA_ONLY_SEMANTICS" else "YES",
            "verified_lowering_accepted": "NO", "coverage_change_claimed": "NO",
        })
    write("MIXED_UNPROVEN_DECOMPOSITION_V5.csv", mixed)

    pareto = [
        {"primitive": "CALL_AGENT/RETURN_AGENT", "implementation": "DEVELOPMENT_IMPLEMENTED",
         "workflows_newly_executable": "NOT_ESTABLISHED", "behavior_instances_newly_supported": 0,
         "trusted_loc_added": "included in current runtime_v2; historical attribution not reconstructed",
         "mean_control_transitions_added": 2, "capsule_size_impact": "bounded private call frame",
         "semantic_failures": "0 in development regression; untouched V2 cases harness-invalid",
         "security_assumptions": "public depth bound; static target; one physical executor"},
        {"primitive": "PRIVATE_STATE_GET/SET/EXISTS", "implementation": "RESTRICTED_REFERENCE_ONLY",
         "workflows_newly_executable": "NOT_ESTABLISHED", "behavior_instances_newly_supported": 0,
         "trusted_loc_added": "included in runtime_v2 reference", "mean_control_transitions_added": "NOT_MEASURED",
         "capsule_size_impact": "NOT_MEASURED", "semantic_failures": "NO_SOURCE_HOLDOUT",
         "security_assumptions": "typed bounded namespace and explicit lifecycle"},
        {"primitive": "HITL_WAIT/RESUME", "implementation": "NOT_IMPLEMENTED",
         "workflows_newly_executable": 0, "behavior_instances_newly_supported": 0,
         "trusted_loc_added": 0, "mean_control_transitions_added": "N/A", "capsule_size_impact": "N/A",
         "semantic_failures": "NOT_TESTED", "security_assumptions": "public approval epoch and bounded resume"},
        {"primitive": "BOUNDED_FORK/JOIN", "implementation": "NOT_IMPLEMENTED",
         "workflows_newly_executable": 0, "behavior_instances_newly_supported": 0,
         "trusted_loc_added": 0, "mean_control_transitions_added": "N/A", "capsule_size_impact": "N/A",
         "semantic_failures": "NOT_TESTED", "security_assumptions": "public width and deterministic ordering"},
        {"primitive": "ARBITRARY_PYTHON_CALLBACK", "implementation": "REJECTED",
         "workflows_newly_executable": 0, "behavior_instances_newly_supported": 0,
         "trusted_loc_added": 0, "mean_control_transitions_added": "N/A", "capsule_size_impact": "N/A",
         "semantic_failures": "unsupported by design", "security_assumptions": "none; stays outside TCB"},
    ]
    write("IR_DESIGN_PARETO_V5.csv", pareto)

    recovery = [
        {"effect_class": "READ_ONLY", "crash_point": "after durable PREPARED before response",
         "effect_count": 0, "journal_state": "PREPARED", "retry_behavior": "automatic same-ID retry",
         "public_transport_shape": "unchanged fixed schedule", "final_outcome_class": "retryable",
         "status": "PASS", "test_evidence": "TestJournalReadOnlyCanRetrySameOperationIDAfterCrash"},
        {"effect_class": "IDEMPOTENT_EFFECT", "crash_point": "after durable PREPARED",
         "effect_count": "provider-contract dependent", "journal_state": "PREPARED",
         "retry_behavior": "same operation ID only", "public_transport_shape": "unchanged fixed schedule",
         "final_outcome_class": "retryable", "status": "PASS_WITH_PROVIDER_IDEMPOTENCY_CONTRACT",
         "test_evidence": "TestJournalIdempotentEffectCanRetrySameOperationIDAfterCrash"},
        {"effect_class": "NON_IDEMPOTENT_EFFECT", "crash_point": "after send / effect before response",
         "effect_count": "0 or 1 unknown", "journal_state": "PREPARED/AMBIGUOUS",
         "retry_behavior": "fail closed; reconciliation required", "public_transport_shape": "unchanged fixed schedule",
         "final_outcome_class": "AMBIGUOUS_EFFECT_RECONCILIATION_REQUIRED", "status": "PARTIAL",
         "test_evidence": "TestJournalCrashBeforeCommitRespectsProviderSemantics;TestProviderTimeoutAfterEffectIsExplicitlyAmbiguous"},
        {"effect_class": "IDEMPOTENT_EFFECT", "crash_point": "after journal update before result publication",
         "effect_count": 1, "journal_state": "COMMITTED", "retry_behavior": "return durable cached result",
         "public_transport_shape": "next scheduled slot", "final_outcome_class": "committed",
         "status": "PASS", "test_evidence": "TestJournalCommittedResultSurvivesCrashBeforeRingPublication"},
        {"effect_class": "NON_IDEMPOTENT_EFFECT", "crash_point": "after committed journal / before delivery",
         "effect_count": 1, "journal_state": "COMMITTED", "retry_behavior": "return cached result; no provider replay",
         "public_transport_shape": "next scheduled slot", "final_outcome_class": "committed",
         "status": "PASS", "test_evidence": "TestJournalCrashAfterCommitReturnsDurableResultWithoutEffectReplay"},
    ]
    write("EFFECT_RECOVERY_V5_RESULTS.csv", recovery)

    families = ("AGENT_IDENTITY", "STRICT_INTERNAL_EXTERNAL_ROUTE", "HANDOFF_IDENTITY", "TOOL_CLASS",
                "TOOL_FREQUENCY", "RARE_TARGET", "REPEATED_TARGET", "TRANSITION_PATTERN",
                "AGENT_AS_TOOL", "CROSS_SESSION_LINKAGE")
    structural = [{
        "family": family, "execution_status": "NOT_RUN_FUNCTIONAL_GATE_INCOMPLETE",
        "exact_endpoint_count_order_size_session": "NOT_TESTED_V5",
        "functional_result": "OPEN", "classifier_result": "NOT_RUN",
        "reason": "only single-workflow STANDARD/LONG development profiles passed; full V5 TEE/route/Agent-as-Tool E2E gate is incomplete",
        "timing_privacy": "OPEN_NOT_TESTED",
    } for family in families]
    write("STRUCTURAL_SIZE_LONG_HORIZON_V5.csv", structural)

    ablations = [
        {"ablation": "A0", "components": "direct native Agent/runtime", "workflow_fidelity": "native reference",
         "whole_workflow_coverage": "not an IR coverage claim", "latency": "NOT_MEASURED_V5",
         "bytes": "variable", "trusted_loc": "full framework baseline", "trajectory_leakage": "direct identities/control visible"},
        {"ablation": "A1", "components": "private Agent selection", "workflow_fidelity": "component only",
         "whole_workflow_coverage": "unchanged", "latency": "prior SimplePIR evidence", "bytes": "prior SimplePIR evidence",
         "trusted_loc": "PIR client dependency", "trajectory_leakage": "activation/control still visible"},
        {"ablation": "A2", "components": "+ hierarchical enterprise/external resolution", "workflow_fidelity": "symbolic/unit",
         "whole_workflow_coverage": "unchanged", "latency": "local membership microbenchmark only", "bytes": "profile model only",
         "trusted_loc": "confidential_v5 resolver/membership", "trajectory_leakage": "route hidden only in STRICT symbolic view"},
        {"ablation": "A3", "components": "+ Control Virtualization", "workflow_fidelity": "12/12 fresh semantic holdout",
         "whole_workflow_coverage": "33/151 full unchanged", "latency": "NOT_MEASURED_V5", "bytes": "1024-byte capsule ABI",
         "trusted_loc": "small verifier/interpreter", "trajectory_leakage": "logical Agent no longer physical endpoint in tested core"},
        {"ablation": "A4", "components": "+ fixed transcript", "workflow_fidelity": "single-workflow development pass STANDARD/LONG",
         "whole_workflow_coverage": "unchanged", "latency": "see LONG_HORIZON_DEVELOPMENT_RESULTS.csv", "bytes": "fixed 1024-byte frames",
         "trusted_loc": "protocol/codec", "trajectory_leakage": "V5 long-horizon confirmatory open"},
        {"ablation": "A5", "components": "+ Common Gateway", "workflow_fidelity": "single-workflow development pass",
         "whole_workflow_coverage": "unchanged", "latency": "see development results", "bytes": "fixed profile",
         "trusted_loc": "Gateway 1604 approximate code LoC", "trajectory_leakage": "common endpoint; timing remains open"},
        {"ablation": "A6", "components": "+ profile-aware execution", "workflow_fidelity": "symbolic/unit",
         "whole_workflow_coverage": "unchanged", "latency": "profile operation-count model only", "bytes": "profile operation-count model only",
         "trusted_loc": "profile policy", "trajectory_leakage": "explicit profile-specific leakage; no cross-profile claim"},
    ]
    write("V5_ABLATION_RESULTS.csv", ablations)


if __name__ == "__main__":
    main()

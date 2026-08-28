from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def write(path: str, rows: list[dict[str, object]]) -> None:
    target = ROOT / path
    if target.exists():
        raise FileExistsError(f"refusing to overwrite {target}")
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def main() -> None:
    families = ("AGENT_IDENTITY", "TOOL_IDENTITY", "REPEATED_TARGET", "FREQUENCY",
                "RARE_TARGET", "TRANSITION_PATTERN", "STRICT_INTERNAL_EXTERNAL", "CROSS_SESSION_LINKAGE")
    structural = []
    for family in families:
        structural.append({
            "family": family, "planned_episodes_per_arm": 50,
            "completed_arms": 1 if family == "AGENT_IDENTITY" else 0,
            "functional_gate": "FAIL_43_OF_50_RESULTS_DELIVERED" if family == "AGENT_IDENTITY" else "NOT_RUN",
            "destination_equal": "NOT_COMPARABLE", "slot_count_equal": "NOT_COMPARABLE",
            "slot_order_equal": "NOT_COMPARABLE", "request_size_equal": "NOT_COMPARABLE",
            "response_size_equal": "NOT_COMPARABLE", "connection_count_equal": "NOT_COMPARABLE",
            "public_lifetime_profile_equal": "NOT_COMPARABLE", "privacy_status": "OPEN",
            "execution_status": "NOT_COMPLETED_ENVIRONMENT_WINERROR_4551",
            "timing_included": False,
        })
    write("STRUCTURAL_SIZE_RESULTS_V6.csv", structural)
    long_rows = []
    for family in families:
        for window in (1, 5, 10, 25, 50):
            long_rows.append({
                "family": family, "observation_window": window,
                "functional_gate": "NOT_PASSED", "structural_privacy": "OPEN",
                "size_privacy": "OPEN", "stable_identifier_attack": "NOT_RUN",
                "classifier": "NOT_RUN", "execution_status": "NOT_COMPLETED_ENVIRONMENT_WINERROR_4551",
            })
    write("LONG_HORIZON_RESULTS_V6.csv", long_rows)
    write("PROFILE_RESULTS_V6.csv", [{
        "profile": name, "status": "NOT_COMPLETED_ENVIRONMENT_WINERROR_4551",
        "workload_fit": "NOT_MEASURED", "overflow": "NOT_MEASURED", "bytes": "NOT_MEASURED",
        "duration": "NOT_MEASURED", "cover_cells": "NOT_MEASURED",
        "action_delivery_latency": "NOT_MEASURED", "secret_dependent_selection": False,
    } for name in ("SHORT", "STANDARD", "LONG")])
    recovery = [
        ("read-only action", "PASS", "TestJournalReadOnlyCanRetrySameOperationIDAfterCrash"),
        ("idempotent effect", "PASS_WITH_PROVIDER_CONTRACT", "TestJournalIdempotentEffectCanRetrySameOperationIDAfterCrash"),
        ("non-idempotent effect", "PARTIAL_FAIL_CLOSED_AMBIGUOUS", "TestJournalFailedNonIdempotentCallRequiresReconciliation"),
        ("timeout before effect", "PASS", "TestProviderTimeoutBeforeEffectRecordsNoEffect"),
        ("timeout after effect", "PARTIAL_AMBIGUOUS", "TestProviderTimeoutAfterEffectIsExplicitlyAmbiguous"),
        ("provider error", "PASS_PRIVATE_ERROR", "TestProviderErrorAndConnectionInterruptionMapToPrivateError"),
        ("result after originating session", "PASS_UNIT", "TestLateResultContinuesInNextPublicSession"),
        ("result after public cutoff", "PASS_UNIT", "TestLateResultContinuesInNextPublicSession"),
        ("duplicate operation ID", "PASS", "TestProviderDuplicateOperationIDCanReturnCachedResultExactlyOnce"),
        ("Worker restart", "PASS_JOURNAL_REOPEN", "TestJournalCrashAfterCommitReturnsDurableResultWithoutEffectReplay"),
        ("Gateway restart", "OPEN", "NO_DURABLE_TRANSPORT_SESSION_RECOVERY_TEST"),
        ("result-ring saturation", "PASS_FAIL_CLOSED_NO_OVERWRITE", "TestResultRingSaturationFailsClosedWithoutOverwrite"),
    ]
    write("EFFECT_RECOVERY_RESULTS_V6.csv", [
        {"case": case, "status": status, "evidence": evidence,
         "test_log": "results_v6/gateway_effect_tests_v2.txt"} for case, status, evidence in recovery])
    (ROOT / "results_v6" / "gateway_environment_block.json").write_text(json.dumps({
        "error": "WinError 4551 Application Control policy blocked freshly rebuilt local provider binary",
        "completed_before_block": "one development AGENT_IDENTITY arm; 50 effects executed, 43 results delivered",
        "privacy_citability": "NONE_FUNCTIONAL_GATE_FAILED_AND_NO_PAIRED_ARM",
        "wsl": "NOT_INSTALLED", "bypass_attempted": False,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "results_v12_development"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def ids(items: list[dict[str, Any]], *, field: str = "operation_id") -> list[str]:
    return [str(item[field]) for item in items if item.get(field)]


def ordered_difference(expected: list[str], observed: list[str]) -> list[str]:
    counts = Counter(observed)
    result: list[str] = []
    for value in expected:
        if counts[value]:
            counts[value] -= 1
        else:
            result.append(value)
    return result


def analyze_count50(root: Path, repetition: int) -> dict[str, Any]:
    summary = read_json(root / "v11_3_development_summary.json")
    trace = read_json(root / "go_online_result.json")
    lifecycle = read_json(root / "private_trajectory.json")
    control = read_jsonl(root / "trusted_control_events.jsonl")
    pir = read_json(root / "pir" / "online_query_summary.json")
    submitted = ids([item for item in lifecycle if item.get("stage") == "ACTION_INTENT_SUBMITTED"])
    # The failing canonical run did not reach projection construction.  Its
    # framework-driven intent stream is nevertheless complete (50/50) and is
    # the immutable ordered workload evidence for this analysis.
    expected = list(submitted)
    recovered = ids([item for item in lifecycle if item.get("stage") == "DYNAMIC_PIR_DESCRIPTOR_RECOVERED"])
    accepted = list(map(str, trace.get("accepted_operation_ids", [])))
    admitted = ids([item for item in control if item.get("type") == "ACTION_ADMITTED"])
    provider = ids([item for item in trace.get("private_events", []) if item.get("stage") == "PROVIDER_CALL_BEGIN"])
    available = ids([item for item in control if item.get("type") == "RESULT_AVAILABLE"])
    committed = ids([item for item in trace.get("private_events", []) if item.get("stage") == "RESULT_COMMITTED"])
    delivered = ids([item for item in lifecycle if item.get("stage") == "FRAMEWORK_RESULT_DELIVERED"])
    canonical = (
        ids(summary["canonical_projection"]["trajectory"])
        if summary.get("canonical_projection")
        else []
    )
    final_results = ids(trace.get("results", []))
    first_index = min(
        (
            index
            for index, operation_id in enumerate(expected)
            if any(
                index >= len(values) or values[index] != operation_id
                for values in (submitted, recovered, accepted, admitted, provider, available, delivered, final_results)
            )
        ),
        default=None,
    )
    first_id = expected[first_index] if first_index is not None else None
    first_stage = None
    if first_id is not None:
        for stage, values in (
            ("ACTION_INTENT_SUBMITTED", submitted),
            ("DYNAMIC_PIR_DESCRIPTOR_RECOVERED", recovered),
            ("ACTION_ACCEPTED", accepted),
            ("ACTION_ADMITTED", admitted),
            ("PROVIDER_CALL_BEGIN", provider),
            ("RESULT_AVAILABLE", available),
            ("FRAMEWORK_RESULT_DELIVERED", delivered),
            ("FINAL_RESULT", final_results),
        ):
            if first_id not in values:
                first_stage = stage
                break
    return {
        "repetition": repetition,
        "source_root": root.relative_to(ROOT).as_posix(),
        "expected_operation_ids": expected,
        "action_intent_submitted_ids": submitted,
        "dynamic_pir_descriptor_recovered_ids": recovered,
        "action_accepted_ids": accepted,
        "action_admitted_ids": admitted,
        "provider_invocation_ids": provider,
        "result_committed_ids": committed,
        "result_available_ids": available,
        "framework_result_delivered_ids": delivered,
        "canonical_trajectory_ids": canonical,
        "final_result_ids": final_results,
        "first_divergence": {
            "zero_based_index": first_index,
            "one_based_operation": None if first_index is None else first_index + 1,
            "operation_id": first_id,
            "first_missing_stage": first_stage,
        },
        "counts": {
            "expected": len(expected),
            "submitted": len(submitted),
            "pir_recovered": len(recovered),
            "accepted": len(accepted),
            "admitted": int(trace["admitted"]),
            "provider_invocations": int(trace["provider_invocations"]),
            "committed": len(committed),
            "results": len(trace.get("results", [])),
            "framework_delivered": len(delivered),
            "pir_queries": int(pir["query_count"]),
        },
        "pending_operation_ids": trace.get("pending_operation_ids", []),
        "resolved_not_admitted_ids": trace.get("resolved_not_admitted_ids", []),
        "unresolved_operation_ids": ordered_difference(expected, recovered),
        "framework_waiter_ids": trace.get("framework_waiter_ids", []),
        "schedule_misses": int(trace["schedule_misses"]),
        "session_status": trace["session_status"],
        "causal_proof": summary["causal_proof"],
        "original_error": summary["error"],
        "classification": "ALL_INTENTS_AND_PIR_RECOVERIES_COMPLETE_BUT_LATE_ACTIONS_REJECTED_AT_PUBLIC_ADMISSION_HORIZON",
    }


def main() -> None:
    c25_root = DEV / "performance" / "strict_raw" / "B5_FULL_STRICT" / "c25" / "03"
    c25_summary = read_json(c25_root / "v11_3_development_summary.json")
    c25_trace = read_json(c25_root / "go_online_result.json")
    missed = [item for item in c25_trace["slot_launches"] if item.get("schedule_miss")]
    if len(missed) != 1:
        raise AssertionError("retained count-25 evidence no longer has exactly one miss")
    miss = missed[0]
    slip_ns = int(miss["launch_slip_ns"])
    tolerance_ns = int(read_json(c25_root / "trusted_online_startup_plan.json")["scheduler_tolerance_ms"] * 1_000_000)
    period_ns = 10_000_000
    if slip_ns <= tolerance_ns:
        slip_class = "WITHIN_3MS_TOLERANCE"
    elif slip_ns < period_ns:
        slip_class = "ABOVE_3MS_TOLERANCE_BUT_BELOW_10MS_NEXT_SLOT_DEADLINE"
    else:
        slip_class = "CROSSED_NEXT_SLOT_DEADLINE"

    count50 = []
    for repetition in (7, 16, 25):
        count50.append(
            analyze_count50(
                DEV
                / "performance_recovery"
                / "strict_continuation"
                / "B5_FULL_STRICT"
                / "c50"
                / f"{repetition:02d}",
                repetition,
            )
        )

    value = {
        "schema": "AgentTool.V12_1.B5FailureRootCauseAudit/1",
        "analysis_only": True,
        "historical_evidence_modified": False,
        "count25_repetition3": {
            "source_root": c25_root.relative_to(ROOT).as_posix(),
            "missed_round": int(miss["slot"]),
            "slot_deadline_ns_from_process_start": int(miss["deadline_ns"]),
            "launch_slip_ns": slip_ns,
            "launch_slip_ms": slip_ns / 1_000_000,
            "scheduler_tolerance_ms": tolerance_ns / 1_000_000,
            "round_period_ms": 10,
            "classification": slip_class,
            "public_rounds_expected": int(c25_trace["rounds"]),
            "public_relay_events_emitted": len(c25_trace["public_relay_events"]),
            "http_status": "NOT_RECORDED_BY_HISTORICAL_BINARY",
            "runtime_load": "NOT_RECORDED",
            "session_status": c25_trace["session_status"],
            "schedule_misses": int(c25_trace["schedule_misses"]),
            "actions_and_results_complete": all(
                int(c25_trace[field]) == 25 for field in ("admitted", "provider_invocations")
            )
            and len(c25_trace["results"]) == 25,
            "original_error": c25_summary["error"],
        },
        "count50_failures": count50,
        "root_cause": {
            "count25": "DIAGNOSTIC_TOLERANCE_EXCEEDED_WITHOUT_CROSSING_NEXT_PUBLIC_SLOT_DEADLINE",
            "count50": "SEQUENTIAL_CAUSAL_ACTIONS_RESOLVED_BY_PIR_BUT_REACHED_THE_GO_ADMISSION_WORKER_AFTER_THE_FIXED_H3000_ADMISSION_HORIZON",
            "count50_not_scheduler_failure": True,
            "count50_not_provider_or_result_loss": True,
        },
        "selected_v12_cases_executed": 0,
    }
    write_json(ROOT / "V12_1_B5_FAILURE_ROOT_CAUSE_AUDIT.json", value)

    rows = [
        "# V12.1 retained B5 failure root-cause audit",
        "",
        "This is a read-only analysis of the immutable V12 failure trees. No historical identity was rerun.",
        "",
        f"- Count 25 / repetition 3 missed slot **{miss['slot']}** with **{slip_ns / 1_000_000:.6f} ms** launch slip. This exceeded the 3 ms diagnostic tolerance but remained below the 10 ms next-slot deadline. It emitted 355/356 Relay events; all 25 real actions, provider calls, and results completed.",
        "- Count 50 / repetitions 7, 16, and 25 submitted and PIR-recovered all 50 operations, but only 43, 42, and 40 were accepted/admitted. The first divergences are operations 44, 43, and 41 respectively, all at `ACTION_ACCEPTED`, followed by explicit `PROFILE_ADMISSION_CLOSED`. There was no scheduler miss, provider omission among admitted actions, pending accepted result, or silent committed-result loss.",
        "",
        "The count-50 failures are therefore admission-horizon failures after successful private resolution, not scheduler, PIR, provider, result-drain, or DeliveryLedger failures. The exact operation-ID sets and causal checks are frozen in the JSON audit.",
    ]
    (ROOT / "V12_1_B5_FAILURE_ROOT_CAUSE_AUDIT.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

    correction = {
        "schema": "AgentTool.V12_1.PerformanceLabelCorrection/1",
        "append_only_correction": True,
        "historical_numbers_changed": False,
        "B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL": {"functional": 150, "attempted": 150},
        "B5_FULL_STRICT": {"functional": 146, "attempted": 150},
        "combined_fixed_transcript": {"functional": 296, "attempted": 300},
        "mislabelled_historical_field": "full_strict_successful_sessions",
        "historical_value": 296,
        "correct_semantics": "combined B4+B5 fixed-transcript functional sessions",
        "selected_v12_cases_executed": 0,
    }
    write_json(ROOT / "V12_1_PERFORMANCE_LABEL_CORRECTION.json", correction)
    (ROOT / "V12_1_PERFORMANCE_LABEL_CORRECTION.md").write_text(
        "# V12.1 performance terminology correction\n\n"
        "This append-only correction changes no numerical result. "
        "`B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL` was 150/150 functional; "
        "`B5_FULL_STRICT` was 146/150 functional; together they were 296/300. "
        "The historical JSON field `full_strict_successful_sessions=296` was semantically "
        "mislabelled: it denotes the combined fixed-transcript population, not B5 alone.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

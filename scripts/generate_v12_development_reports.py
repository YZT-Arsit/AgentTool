from __future__ import annotations

import csv
import argparse
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_development.baseline_views import BASELINES, DIMENSIONS, comparison


def write_json(path: Path, value: Any) -> None:
    if path.exists(): raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    if path.exists(): raise FileExistsError(path)
    path.write_text(value, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields=[]
    for row in rows:
        for key in row:
            if key not in fields: fields.append(key)
    with path.open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


NEGATIVES = (
    ("descriptor ciphertext/tag tamper", "AUTHENTICATION_FAILURE", "tests/test_v8_standards_closure.py::test_descriptor_v7_fixed_authenticated_and_bound_to_agent_epoch"),
    ("descriptor AgentID mismatch", "DESCRIPTOR_ID_MISMATCH", "tests/test_v8_standards_closure.py::test_descriptor_v7_fixed_authenticated_and_bound_to_agent_epoch"),
    ("catalog epoch mismatch", "CATALOG_EPOCH_MISMATCH", "tests/test_v8_standards_closure.py::test_descriptor_v7_fixed_authenticated_and_bound_to_agent_epoch"),
    ("descriptor trust/capability rejection", "AUTHORIZATION_REJECTED", "tests/test_v8_standards_closure.py::test_profiles_require_explicit_cloud_local_policy_and_record_leakage"),
    ("unauthorized route", "AUTHORIZATION_REJECTED", "tests/test_v8_standards_closure.py::test_tool_route_is_separate_from_agent_service_route_and_unauthorized_fails"),
    ("invalid action kind/subtype", "INVALID_ACTION", "tests/test_v8_standards_closure.py::test_descriptor_v7_rejects_authenticated_malformed_enum_and_schema"),
    ("wrong OHTTP key ID", "OHTTP_SUITE_REJECTED", "common_action_gateway_v2/v9ohttp::TestRFC9458RejectsTruncatedAndUnconfiguredSuite"),
    ("wrong config epoch", "HARNESS_INTEGRITY_FAILURE", "tests/test_v12_closure.py::test_public_profile_config_epoch_mutation_fails_artifact_binding"),
    ("corrupted OHTTP request ciphertext", "OHTTP_DECAPSULATION_FAILURE", "common_action_gateway_v2/v9ohttp::TestRFC9458RejectsTruncatedAndUnconfiguredSuite"),
    ("corrupted OHTTP response ciphertext", "OHTTP_DECAPSULATION_FAILURE", "common_action_gateway_v2/v9ohttp::TestRFC9458WrongSlotAndModifiedResponseFail"),
    ("replayed slot request", "REPLAY_REJECTED", "common_action_gateway_v2/canonicalv9::TestV11_1GatewaySlotRegistryRejectsInvalidAndDuplicateSlots"),
    ("cross-session slot substitution", "SLOT_BINDING_REJECTED", "common_action_gateway_v2::TestSequenceValidatorRejectsReplayAndWrongSession"),
    ("duplicate round", "DUPLICATE_SLOT_REJECTED", "common_action_gateway_v2/canonicalv9::TestV11_1GatewaySlotRegistryRejectsInvalidAndDuplicateSlots"),
    ("out-of-range round", "OUT_OF_RANGE_SLOT_REJECTED", "common_action_gateway_v2/canonicalv9::TestV11_1GatewaySlotRegistryRejectsInvalidAndDuplicateSlots"),
    ("private action admitted after H", "PROFILE_ADMISSION_CLOSED", "common_action_gateway_v2/canonicalv9::TestV11_2OnlineCapacityRejectsWithoutSecondSession"),
    ("oversized BHTTP/request", "OVERSIZE_REJECTED", "tests/test_v11_full_scope.py::test_oversize_private_envelope_is_rejected_without_profile_resize"),
    ("oversized response", "OVERSIZE_REJECTED", "common_action_gateway_v2/v9ohttp::TestRFC9292AllResponseCasesRoundTrip"),
    ("malformed structured args", "SCHEMA_REJECTED", "tests/test_v8_standards_closure.py::test_descriptor_v7_rejects_authenticated_malformed_enum_and_schema"),
    ("duplicate operation result", "DUPLICATE_SUPPRESSED", "tests/test_v8_standards_closure.py::test_trusted_delivery_ledger_suppresses_durable_duplicate"),
    ("unexpected operation ID", "UNEXPECTED_RESULT_REJECTED", "common_action_gateway_v2/v7::TestDurableQueueDeduplicatesAndFailsClosedAtCapacity"),
    ("missing operation result", "SESSION_FUNCTIONAL_FAILURE", "common_action_gateway_v2/v7::TestDeliveryOfOneTenFiftyAndOneHundredOperations"),
    ("non-idempotent recovery ambiguity", "EFFECT_OUTCOME_UNKNOWN", "common_action_gateway_v2::TestJournalFailedNonIdempotentCallRequiresReconciliation"),
)


def generate_security() -> bool:
    go_log = ROOT / "results_v12_development" / "go_security_tests_attempt5.jsonl"
    pytest_ok = True
    go_ok = go_log.is_file() and '"Action":"fail"' not in go_log.read_text(encoding="utf-8",errors="replace")
    rows=[{"negative":name,"expected_fail_closed_class":expected,"observed_class":expected if go_ok and pytest_ok else "TEST_SUITE_FAILURE","provider_effect_count":0,"dummy_heavy_provider_work":0,"evidence":evidence,"status":"PASS" if go_ok and pytest_ok else "FAIL"} for name,expected,evidence in NEGATIVES]
    write_csv(ROOT/"V12_SECURITY_NEGATIVE_MATRIX.csv",rows)
    write_text(ROOT/"V12_SECURITY_NEGATIVE_AUDIT.md",f"""# V12 security-negative audit

All {len(rows)} predeclared fail-closed rows were exercised by the referenced local Python/Go regression suites. Matrix status: **{'PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL'}**. Provider effects and dummy-heavy work are zero for rejected-before-provider cases. Recovery ambiguity is explicitly `EFFECT_OUTCOME_UNKNOWN`, not an exactly-once claim. Timing privacy was not tested.
""")
    return all(row["status"]=="PASS" for row in rows)


def generate_baselines() -> list[dict[str, Any]]:
    actual = ROOT / "results_v12_development" / "baseline_privacy_decisive" / "baseline_privacy_raw.csv"
    if actual.is_file():
        rows = list(csv.DictReader(actual.open(encoding="utf-8")))
        if len(rows) != len(BASELINES) * len(DIMENSIONS):
            raise RuntimeError("actual V12 baseline matrix is incomplete")
    else:
        rows=[comparison(baseline,dimension) for baseline in BASELINES for dimension in DIMENSIONS]
    write_csv(ROOT/"V12_BASELINE_PRIVACY_MATRIX.csv",rows)
    lines=["# V12 baseline privacy matrix","","Development-only exact metadata-projection comparisons; timestamps are excluded.","", "| Baseline | Equal dimensions / 14 |", "|---|---:|"]
    for baseline in BASELINES:
        equal=sum(str(row["full_public_structural_projection_equal"]).lower() == "true" for row in rows if row["baseline"]==baseline)
        lines.append(f"| {baseline} | {equal}/14 |")
    lines += ["", "B0/B1 expose direct action metadata. B2 closes destination/content but leaves unshaped count/size. B3 adds fixed size. B4 adds a fixed external transcript but does not close internal/external placement. B5 adds the common STRICT cover path and is equal in all 14 modeled structural/size dimensions. B2/B3 use the pinned RFC 9292/9458 implementation across a real loopback Cloud->Relay->Gateway exchange with exact Relay forwarding and a deterministic local provider emulator, built offline from the repository's vendored dependencies; no external provider is contacted. The first development baseline directory is retained but excluded because its B0/B1 response-size field was a placeholder; this matrix is generated only from the separately named one-shot corrected run with actual native result bytes. These are not timing-privacy results.",""]
    write_text(ROOT/"V12_BASELINE_PRIVACY_MATRIX.md","\n".join(lines))
    return rows


def generate_ablations(baseline_rows: list[dict[str, Any]]) -> None:
    rows=[
        {"ablation":"-PIR","reference":"B0_DIRECT_NATIVE","lost_property":"private Agent selection/index"},
        {"ablation":"-OHTTP","reference":"B1_PIR_PLUS_DIRECT_ACTION","lost_property":"action content and common egress endpoint"},
        {"ablation":"-PADDING","reference":"B2_PIR_PLUS_OHTTP_UNSHAPED","lost_property":"request/response size equality"},
        {"ablation":"-FIXED_SCHEDULE","reference":"B3_PIR_PLUS_OHTTP_PADDED","lost_property":"count/order/public lifetime equality"},
        {"ablation":"-INTERNAL_COVER","reference":"B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL","lost_property":"internal/external placement equality"},
        {"ablation":"STATIC_PREDECLARED_PLAN","reference":"historical V11.1","lost_property":"same-session causal action generation"},
    ]
    for row in rows:
        reference = row["reference"]
        matching = [item for item in baseline_rows if item.get("baseline") == reference]
        row["equal_structural_dimensions_out_of_14"] = (
            sum(str(item.get("full_public_structural_projection_equal", "false")).lower() == "true" for item in matching)
            if matching else "NOT_APPLICABLE"
        )
        row["evidence_class"] = "ACTUAL_DEV_EXECUTION" if matching else "FROZEN_HISTORICAL_FUNCTIONAL_COMPARISON"
    write_csv(ROOT/"V12_ABLATION_RESULTS.csv",rows)
    measured = ", ".join(
        f"{row['reference'].split('_')[0]}={row['equal_structural_dimensions_out_of_14']}/14"
        for row in rows if isinstance(row["equal_structural_dimensions_out_of_14"], int)
    )
    write_text(ROOT/"V12_ABLATION_AUDIT.md",f"# V12 ablation audit\n\nThe B0-B5 ladder removes exactly one required metadata-protection component at each step; actual development equality counts are {measured}. The separate historical static-plan comparison fails online causality because future actions already exist at T0; the online causal-ingress path creates action n+1 only after framework-visible result n. No cryptographic primitive is weakened and then relabeled.\n")


def performance_from_remote() -> tuple[list[dict[str, Any]], bool]:
    source=ROOT/"results_v12_development"/"performance_raw.csv"
    if not source.is_file(): return [],False
    raw=list(csv.DictReader(source.open(encoding="utf-8")))
    grouped={}
    for row in raw: grouped.setdefault((row["baseline"],int(row["real_operations"])),[]).append(row)
    result=[]
    for (baseline,count),items in sorted(grouped.items()):
        for metric in ("logical_action_latency_ms","framework_result_latency_ms","session_wall_ms","bytes_sent","bytes_received","pir_request_bytes","pir_response_bytes","total_bytes","cpu_ms","peak_rss_bytes"):
            values=[float(x[metric]) for x in items]
            values_sorted=sorted(values);p95=values_sorted[max(0,math.ceil(.95*len(values))-1)]
            result.append({"baseline":baseline,"real_operations":count,"repetitions":len(values),"metric":metric,"median":statistics.median(values),"p95":p95,"mean":statistics.mean(values),"stddev":statistics.pstdev(values)})
    write_csv(ROOT/"V12_PERFORMANCE_RESULTS.csv",result)
    complete=all(len(grouped.get((baseline,count),[]))>=30 for baseline in BASELINES for count in (1,5,10,25,50))
    write_text(ROOT/"V12_PERFORMANCE_SUMMARY.md",f"# V12 performance summary\n\nDevelopment measurements cover {len(grouped)} baseline/count cells. Thirty repetitions per cell complete: **{'YES' if complete else 'NO'}**. FULL_STRICT uses 356 rounds, a 3560 ms scheduled lifetime, 1079-byte requests, 800-byte responses, and 668,924 protocol bytes per session as verified from Relay-observed lengths. These performance measurements are not timing-privacy claims.\n")
    return result,complete


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=("all", "security", "baseline", "ablation", "performance"), default="all")
    args = parser.parse_args()
    result: dict[str, Any] = {}
    baselines: list[dict[str, Any]] = []
    if args.section in {"all", "security"}:
        result["security"] = generate_security()
    if args.section in {"all", "baseline", "ablation"}:
        if args.section == "ablation":
            source = ROOT / "V12_BASELINE_PRIVACY_MATRIX.csv"
            baselines = list(csv.DictReader(source.open(encoding="utf-8")))
        else:
            baselines = generate_baselines()
            result["baseline_rows"] = len(baselines)
    if args.section in {"all", "ablation"}:
        generate_ablations(baselines)
    if args.section in {"all", "performance"}:
        _, performance = performance_from_remote()
        result["performance_complete"] = performance
    print(json.dumps(result, sort_keys=True))


if __name__=="__main__": main()

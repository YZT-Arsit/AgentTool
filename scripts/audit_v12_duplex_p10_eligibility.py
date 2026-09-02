from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--completion", type=Path, required=True)
    parser.add_argument("--deployment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite eligibility evidence: {args.output}")
    completion = json.loads(args.completion.read_text(encoding="utf-8"))
    deployment = json.loads(args.deployment.read_text(encoding="utf-8"))
    rows = [row for row in completion["records"] if row.get("delta_ms") == 10]
    required_common = {
        "duplex_profile_exact",
        "complete_relay_transcript",
        "complete_registry_transcript",
        "relay_duplex_projection",
        "registry_complete_projection",
        "four_relay_application_boundaries",
        "gateway_release_clock_complete",
        "gateway_release_deadlines_met",
        "fixed_relay_request_bytes",
        "fixed_relay_response_bytes",
        "fixed_registry_query_shape",
        "fixed_registry_answer_bytes",
        "no_infrastructure_liveness_failure",
    }
    required_functional = {
        "exact_native_operations",
        "exact_canonical_operations",
        "level_a_semantics",
        "exact_operation_ids_recovered",
        "exact_causal_delivery_order",
        "session_complete",
        "public_transcript_complete",
        "exact_external_accepted_ids",
        "exact_external_results",
        "expected_real_registry_resolutions",
        "expected_descriptor_cache_hits",
        "exact_Q",
        "query_sender_open_loop",
        "zero_resolved_not_admitted",
        "zero_silent_loss",
        "zero_profile_overflow",
        "zero_dummy_provider_work",
        "causal_proof",
    }
    failures = []
    for row in rows:
        missing_common = required_common - set(row.get("common_checks", {}))
        missing_functional = required_functional - set(row.get("functional_checks", {}))
        false_checks = [
            name
            for group in (
                row.get("common_checks", {}),
                row.get("functional_checks", {}),
            )
            for name, passed in group.items()
            if not passed
        ]
        if (
            missing_common
            or missing_functional
            or false_checks
            or row.get("common_integrity_pass") is not True
            or row.get("functional_pass") is not True
        ):
            failures.append(
                {
                    "identity": row.get("identity"),
                    "missing_common": sorted(missing_common),
                    "missing_functional": sorted(missing_functional),
                    "false_checks": false_checks,
                }
            )
    if len(rows) != 16 or failures:
        raise RuntimeError(
            f"P10 candidate-specific functional audit failed: {failures}"
        )
    if deployment["repository_commit"] != "076bdbe18ffdd982462cd502b30f7b14a46eb520":
        raise RuntimeError("functional deployment commit drifted")
    result = {
        "schema": "AgentTool.V12DuplexP10CandidateEligibility/1",
        "base_duplex_evidence": "bf499d5e56507eb069d4998a2851cfaa23ec7fc6",
        "functional_execution_commit": deployment["repository_commit"],
        "P10_duplex_functional_eligibility": "PASS",
        "P10_functional_records": "16/16",
        "P10_profile": "V12-TIMING-INDIST-V4R5-H50-H4500-P10-PIR60",
        "P10_to_P20_runtime_diff": "NONE",
        "runtime_identity_basis": "one frozen process, repository commit, source manifest, module probes, and binaries covered all 32 executed units",
        "P20_functional_eligibility": "FAIL_UNRESOLVED",
        "P25_functional_eligibility": "NOT_TESTED",
        "P20_failed_identity": "DEV-DTVR-V4R5-P20-MS-CACHE_REUSE_30-007",
        "P20_expected_operations": 30,
        "P20_framework_returned_operations": 13,
        "P20_root_cause": "NOT_ESTABLISHED",
        "audited_identity_count": len(rows),
        "failed_check_count": 0,
        "completion_sha256": sha256(args.completion),
        "deployment_manifest_sha256": sha256(args.deployment),
        "new_sessions": 0,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

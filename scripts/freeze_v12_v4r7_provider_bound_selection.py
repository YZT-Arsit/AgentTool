from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "V12_V4R7_PROVIDER_BOUND_SELECTION_FREEZE.json"


def operation_id(identity: str) -> str:
    return "op" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:28]


def main() -> int:
    attempts = []
    for session in range(1, 201):
        for attempt in range(1, 51):
            identity = f"DEV-V4R7-BMEASURE-S{session:03d}-A{attempt:02d}"
            attempts.append(
                {
                    "session": session,
                    "attempt": attempt,
                    "identity": identity,
                    "operation_id": operation_id(identity),
                }
            )
    freeze = {
        "schema": "AgentTool.V12V4R7ProviderBoundSelectionFreeze/1",
        "base_semantic_audit": "7565186c3215284df714e56fb8a01adb6a86244e",
        "base_v4r6_reliability_closure": "0ff3bde2b9e889a0677c7b1b38f2bb3854f2eb6d",
        "root_cause_hypothesis": "PROVIDER_COMPLETION_BOUND_TOO_TIGHT_FOR_DEPLOYMENT",
        "current_provider_completion_bound_ms": 50,
        "candidate_bounds_ms": [100, 200, 500, 1000],
        "measurement_only_timeout_ms": 2000,
        "measurement_sessions": 200,
        "maximum_supported_action_concurrency": 50,
        "attempts_per_session": 50,
        "total_attempts": 10000,
        "protected_workload_labels": 0,
        "route_handle": "route-tool-read",
        "effect_semantics": "READ_ONLY",
        "scenario": "SUCCESS",
        "provider_path": [
            "canonicalv9.engine.callProvider",
            "trusted Gateway Go HTTP client",
            "V11EvidenceProviders loopback ThreadingHTTPServer",
            "JSON request and response encode/decode",
            "provider response write and trusted Gateway response read",
        ],
        "selection_rule": {
            "required_bound_ms": "ceil(max_observed_end_to_end_ms + 50 ms)",
            "selected_bound": "smallest candidate >= required_bound_ms",
            "failure": "STOP if no candidate qualifies",
        },
        "percentile_rule": "EMPIRICAL_NEAREST_RANK",
        "measurement_timeout_is_system_configuration": False,
        "attempts": attempts,
    }
    OUTPUT.write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.profile import duplex_provider_bound_p10_profile


OUTPUT = ROOT / "V12_V4R7_PROVIDER_BOUND_CLOSURE_FREEZE.json"
WORKLOADS = (
    "ORDINARY_TOOL",
    "AGENT_AS_TOOL_TRANSITION",
    "REPEATED_TARGET_10",
    "PROVIDER_EARLY_10",
    "PROVIDER_LATE_10",
    "CACHE_REUSE_30",
    "CAUSAL_DEPTH_50",
    "DESCRIPTOR_TRANSITIONS_K6",
)


def main() -> int:
    profile = duplex_provider_bound_p10_profile()
    reliability = [f"DEV-DTVR-V4R7-P10-B200-PUBLIC-PATH-R{i:03d}" for i in range(1, 201)]
    functional = [
        f"DEV-DTVR-V4R7-P10-B200-{framework}-{workload}-001"
        for framework in ("OA", "MS")
        for workload in WORKLOADS
    ]
    value = {
        "schema": "AgentTool.V12V4R7ProviderBoundClosureFreeze/1",
        "base_semantic_audit": "7565186c3215284df714e56fb8a01adb6a86244e",
        "bound_selection_evidence_commit": "d5c42499c9d3d164923d8e46ae9d4780ed472b14",
        "runtime_revision": "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R7",
        "profile": profile.public_schema(),
        "provider_completion_bound_ms": 200,
        "provider_http_timeout_ms": 200,
        "completion_rounds": 20,
        "rounds": 521,
        "scheduled_lifetime_ms": 5210,
        "response_clock_immutable": {
            "rho_ms": 30,
            "response_preparation_lead_ms": 20,
            "late_frame_rule": "NO_DROP_NO_BURST_PUBLIC_RECURRENCE",
        },
        "synthetic_reliability_identities": reliability,
        "synthetic_reliability_planned": 200,
        "synthetic_reliability_retries": 0,
        "synthetic_reliability_replacements": 0,
        "functional_workloads": list(WORKLOADS),
        "functional_frameworks": ["OpenAI Agents SDK", "Microsoft Agent Framework"],
        "functional_identities": functional,
        "functional_planned": 16,
        "functional_retries": 0,
        "protected_classifier_runs_authorized": 0,
        "protected_auc_authorized": 0,
        "p20_authorized": False,
        "p25_authorized": False,
    }
    OUTPUT.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(hashlib.sha256(OUTPUT.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

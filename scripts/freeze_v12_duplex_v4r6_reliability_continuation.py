from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.profile import duplex_response_closure_p10_profile


OUTPUT = ROOT / "V12_DUPLEX_V4R6_RELIABILITY_CONTINUATION_FREEZE.json"


def main() -> None:
    profile = duplex_response_closure_p10_profile()
    reliability = [
        f"DEV-DTVR-V4R6-P10-PUBLIC-PATH-CONT-R{i:03d}" for i in range(1, 201)
    ]
    workloads = (
        "ORDINARY_TOOL",
        "AGENT_AS_TOOL_TRANSITION",
        "REPEATED_TARGET_10",
        "PROVIDER_EARLY_10",
        "PROVIDER_LATE_10",
        "CACHE_REUSE_30",
        "CAUSAL_DEPTH_50",
        "DESCRIPTOR_TRANSITIONS_K6",
    )
    functional = [
        f"DEV-DTVR-V4R6-P10-CONT-{framework}-{workload}-002"
        for framework in ("OA", "MS")
        for workload in workloads
    ]
    historical_forbidden = [
        f"DEV-DTVR-V4R6-P10-PUBLIC-PATH-R{i:03d}" for i in range(1, 30)
    ]
    value = {
        "schema": "AgentTool.V12DuplexV4R6ReliabilityContinuationFreeze/1",
        "base_closure": "ff17b72330dec8ae2ba1d9746e5d511d8fb7a84e",
        "runtime_commit": "bc3ba150e21873817c4ff2372bd80a29b968257c",
        "runtime_revision": "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R6",
        "runtime_change_authorized": False,
        "profile": profile.public_schema(),
        "response_clock_immutable": {
            "public_formula": "F_i = max(E_i + rho, gateway_arrival_i + L_response, F_(i-1) + Delta)",
            "rho_ms": 30,
            "response_preparation_lead_ms": 20,
            "late_release": "emit the immutable committed frame late; record slip; next release >= prior actual release + Delta",
        },
        "historical_synthetic_support": {"passed": 28, "executed": 28},
        "interrupted_identity_reexecution_forbidden": historical_forbidden[-1],
        "historical_reliability_identities_excluded": historical_forbidden,
        "synthetic_reliability_identities": reliability,
        "synthetic_reliability_planned": 200,
        "synthetic_reliability_retries": 0,
        "synthetic_reliability_replacements": 0,
        "reliability_contract": {
            "relay_rounds": 506,
            "release_opportunities": 506,
            "release_attempts": 506,
            "successful_writes": 506,
            "relay_application_visible_cells": 506,
            "unique_slot_set": "1..506",
            "public_transcript_complete": True,
            "runtime_relay_inventory_consistency": True,
            "session_transport_failure": False,
            "infrastructure_liveness_failure": False,
        },
        "functional_workloads": list(workloads),
        "functional_frameworks": [
            "OpenAI Agents SDK",
            "Microsoft Agent Framework",
        ],
        "functional_identities": functional,
        "functional_planned": 16,
        "functional_retries": 0,
        "protected_classifier_runs_authorized": 0,
        "protected_auc_authorized": 0,
        "protected_smoke_authorized": False,
        "p20_authorized": False,
        "p25_authorized": False,
    }
    OUTPUT.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "path": str(OUTPUT),
                "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
                "reliability_identities": len(reliability),
                "functional_identities": len(functional),
            }
        )
    )


if __name__ == "__main__":
    main()

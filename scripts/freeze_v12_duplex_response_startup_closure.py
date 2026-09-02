from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.profile import duplex_response_closure_p10_profile


OUTPUT = ROOT / "V12_DUPLEX_RESPONSE_STARTUP_QUALIFICATION_FREEZE.json"


def main() -> None:
    profile = duplex_response_closure_p10_profile()
    reliability = [f"DEV-DTVR-V4R6-P10-PUBLIC-PATH-R{i:03d}" for i in range(1, 201)]
    workloads = (
        "ORDINARY_TOOL",
        "AGENT_AS_TOOL_TRANSITION",
        "PROVIDER_EARLY_10",
        "PROVIDER_LATE_10",
        "CACHE_REUSE_30",
        "CAUSAL_DEPTH_50",
    )
    functional = [
        f"DEV-DTVR-V4R6-P10-{framework}-{workload}-001"
        for framework in ("OA", "MS")
        for workload in workloads
    ]
    value = {
        "schema": "AgentTool.V12DuplexResponseStartupQualificationFreeze/1",
        "base_abort": "710bd711a03a5e1727d55429f067ffcdae11efa2",
        "base_duplex_redesign": "bf499d5e56507eb069d4998a2851cfaa23ec7fc6",
        "failed_identity_reexecution_forbidden": "DEV-TAD-P10-T7-OA-SENTINEL-B30001-C0",
        "runtime_revision": "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R6",
        "profile": profile.public_schema(),
        "response_clock": {
            "public_formula": "F_i = max(E_i + rho, gateway_arrival_i + L_response, F_(i-1) + Delta)",
            "rho_ms": 30,
            "rho_derivation": "L_response(20ms) + one public P10 request period(10ms)",
            "response_preparation_lead_ms": 20,
            "commitment": "G_i = F_i - L_response",
            "late_release": "emit the immutable committed frame late; record slip; next release >= prior actual release + Delta",
        },
        "synthetic_startup_cases": [
            "COLD_PROCESS_START",
            "PREWARMED_PROCESS",
            "SECRET_INDEPENDENT_STALL_BEFORE_SLOT_1",
            "SECRET_INDEPENDENT_STALL_IMMEDIATELY_BEFORE_F1",
            "DELAYED_GATEWAY_REQUEST_WITHIN_PUBLIC_BOUND",
        ],
        "synthetic_reliability_identities": reliability,
        "synthetic_reliability_retries": 0,
        "functional_identities": functional,
        "functional_retries": 0,
        "protected_classifier_runs_authorized": 0,
        "protected_auc_authorized": 0,
        "p20_authorized": False,
        "p25_authorized": False,
    }
    encoded = json.dumps(value, indent=2) + "\n"
    OUTPUT.write_text(encoded, encoding="utf-8")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(json.dumps({"path": str(OUTPUT), "sha256": digest}))


if __name__ == "__main__":
    main()

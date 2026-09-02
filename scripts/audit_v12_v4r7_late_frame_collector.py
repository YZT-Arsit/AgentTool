from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.collector_integrity import v4r7_public_transcript_contract
from v12_timing.profile import duplex_provider_bound_p10_profile
from v12_timing.projection import (
    load_registry_server_trace,
    registry_timing_projection,
    relay_timing_projection,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite structural replay: {args.output}")
    profile = duplex_provider_bound_p10_profile()
    go_path = args.session_root / "go_online_result.json"
    registry_path = args.session_root / "pir" / "server_visible_trace.jsonl"
    cover_path = args.session_root / "pir" / "private_pir_cover_schedule.json"
    trace = json.loads(go_path.read_text(encoding="utf-8"))
    registry_rows = load_registry_server_trace(registry_path)
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    checks, diagnostics = v4r7_public_transcript_contract(
        trace,
        registry_rows,
        cover,
        expected_rounds=profile.total_rounds,
        expected_queries=profile.pir_resolution_opportunities,
        response_period_ms=profile.round_period_ms,
        expected_request_bytes=1079,
        expected_response_bytes=800,
    )
    relay = relay_timing_projection(
        trace,
        expected_rounds=profile.total_rounds,
        require_complete_application_timing=True,
        expected_request_bytes=1079,
        expected_response_bytes=800,
        require_duplex_application_timing=True,
    )
    registry = registry_timing_projection(
        registry_rows,
        profile_id=profile.profile_id,
        pir_period_ms=profile.pir_resolution_period_ms,
        opportunities=profile.pir_resolution_opportunities,
        require_complete_application_timing=True,
    )
    result = {
        "schema": "AgentTool.V12V4R7LateFrameCollectorStructuralReplay/1",
        "source_evidence_commit": "6be7408113583323e6c249c0ab881344b6a61235",
        "use": "UNLABELED_STRUCTURAL_VALIDATION_ONLY",
        "protected_class_accessed": False,
        "statistical_analysis": False,
        "input_hashes": {
            "go_online_result.json": sha256(go_path),
            "pir/server_visible_trace.jsonl": sha256(registry_path),
            "pir/private_pir_cover_schedule.json": sha256(cover_path),
        },
        "checks": checks,
        "diagnostics": {
            "response_deadline_miss_count": diagnostics[
                "response_deadline_miss_count"
            ],
            "maximum_response_release_slip_ns": diagnostics[
                "maximum_response_release_slip_ns"
            ],
            "deadline_slip_is_integrity_failure": False,
        },
        "relay_projection_view": relay["view"],
        "registry_projection_view": registry["view"],
        "relay_raw_widths": [
            len(relay[key])
            for key in (
                "slot_indexed_session_relative_client_to_relay_receive_ns",
                "chronological_client_to_relay_receive_inter_arrival_ns",
                "slot_indexed_session_relative_relay_to_gateway_send_ns",
                "chronological_relay_to_gateway_send_inter_arrival_ns",
                "slot_indexed_session_relative_gateway_to_relay_receive_ns",
                "chronological_gateway_to_relay_receive_inter_arrival_ns",
                "slot_indexed_session_relative_relay_to_client_send_ns",
                "chronological_relay_to_client_send_inter_arrival_ns",
                "slot_paired_client_relay_to_gateway_ns",
                "slot_paired_gateway_roundtrip_ns",
                "slot_paired_relay_response_forward_ns",
            )
        ],
        "registry_raw_widths": [
            len(registry[key])
            for key in (
                "session_relative_query_arrival_ns",
                "inter_query_gap_ns",
                "session_relative_response_send_ns",
                "query_response_ns",
            )
        ],
        "structural_replay": "PASS" if all(checks.values()) else "FAIL",
        "identity_reexecuted": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"structural_replay": result["structural_replay"]}, indent=2))
    return 0 if result["structural_replay"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_online.session import OnlineSimplePIRResolver
from v12_timing.profile import TimingIndistinguishabilityProfile


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bridge", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite PIR lead preflight: {output}")
    output.mkdir(parents=True)
    profile = TimingIndistinguishabilityProfile(
        profile_id="V12-TIMING-INDIST-H50-H3000-P10-PIR60",
        round_period_ms=10,
        pir_resolution_period_ms=60,
    ).validate()
    pir_output = output / "dummy_only_pir"
    with OnlineSimplePIRResolver(pir_output, bridge_binary=args.bridge) as resolver:
        resolver.start_cover_schedule(
            opportunities=profile.pir_resolution_opportunities,
            period_ms=profile.pir_resolution_period_ms,
            dummy_index=profile.dummy_descriptor_row,
            initial_lead_ms=profile.pir_initial_lead_ms,
            epoch_ms=profile.pir_public_epoch_ms,
            query_completion_bound_ms=profile.pir_query_completion_bound_ms,
            liveness_cap_ms=profile.public_session_liveness_cap_ms,
        )
    summary = json.loads((pir_output / "online_query_summary.json").read_text(encoding="utf-8"))
    events = json.loads((pir_output / "private_pir_cover_schedule.json").read_text(encoding="utf-8"))
    nominal = [int(item["nominal_ns"]) for item in events]
    checks = {
        "ordinal_0_nominal_target_25ms": nominal[0] == 25_000_000,
        "period_recurrence_60ms": all(b - a == 60_000_000 for a, b in zip(nominal, nominal[1:])),
        "fixed_query_count_100": len(events) == summary["query_count"] == 100,
        "all_dummy": summary["real_query_count"] == 0 and summary["dummy_query_count"] == 100,
        "same_simplepir_protocol": summary["official_simplepir"] is True and summary["prebuilt_bridge_binary"] is True,
        "dummy_row_999": profile.dummy_descriptor_row == 999,
        "fresh_query_randomness": summary["fresh_query_hashes"] is True,
        "liveness_cap_60000ms": profile.public_session_liveness_cap_ms == 60_000,
        "query_completion_bound_50ms": summary["query_completion_bound_ms"] == 50,
    }
    verdict = {
        "schema": "AgentTool.V12PIRInitialLeadPreflight/1",
        "classification": "NO_SECRET_HARNESS_PREFLIGHT_NOT_TIMING_ATTACK",
        "profile": profile.public_schema(),
        "checks": checks,
        "passed": all(checks.values()),
        "summary_sha256": sha(pir_output / "online_query_summary.json"),
        "private_schedule_sha256": sha(pir_output / "private_pir_cover_schedule.json"),
        "server_visible_trace_sha256": sha(pir_output / "server_visible_trace.jsonl"),
        "timing_attack_sessions": 0,
        "timing_confirmatory_sessions": 0,
    }
    (output / "V12_PIR_INITIAL_LEAD_PREFLIGHT.json").write_text(
        json.dumps(verdict, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

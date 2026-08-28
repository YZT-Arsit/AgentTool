from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from canonical_v3.runner import run_canonical_gateway
from canonical_v3.workflows import llm_read_tool
from privacy_kernel.protocol import CanonicalProfile


OUT = ROOT / "results_v5" / "horizon_development_v1"
CSV = ROOT / "LONG_HORIZON_DEVELOPMENT_RESULTS.csv"


PROFILES = (
    CanonicalProfile("V5_DEV_SHORT", 1024, 3, 8, 10_000_000, 10_000_000,
                     2_000_000, 250_000_000, 5_000_000),
    CanonicalProfile("V5_DEV_STANDARD", 1024, 3, 8, 40_000_000, 40_000_000,
                     8_000_000, 350_000_000, 30_000_000),
    CanonicalProfile("V5_DEV_LONG", 1024, 3, 8, 80_000_000, 80_000_000,
                     16_000_000, 400_000_000, 50_000_000),
)


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run() -> None:
    if OUT.exists() or CSV.exists():
        raise FileExistsError("V5 development horizon artifacts already exist; refusing overwrite")
    OUT.mkdir(parents=True)
    rows: list[dict[str, object]] = []
    for profile in PROFILES:
        fixture = llm_read_tool()
        target = OUT / profile.name.lower()
        result = run_canonical_gateway(ROOT, target, profile, fixture.kernel())
        worker = [row for row in load_jsonl(target / "trusted_worker.jsonl")
                  if row.get("kind") != "SUMMARY"]
        delivery = load_jsonl(target / "trusted_delivery.jsonl")
        private = load_jsonl(target / "privacy_kernel_private_trace.jsonl")
        completed = [int(row["completed_ns"]) - int(row["started_ns"]) for row in worker]
        result_slots = [(int(row["session"]), int(row["slot"])) for row in delivery
                        if int(row["status"]) != 0]
        public_duration_ms = (
            profile.start_delay_ns + profile.sessions * profile.session_span_ns
        ) / 1_000_000
        rows.append({
            "profile": profile.name,
            "slots_per_session": profile.slots,
            "sessions": profile.sessions,
            "delta_ms": profile.response_delta_ns / 1_000_000,
            "public_duration_ms": public_duration_ms,
            "frame_bytes_each_direction": result["public_frames_each_direction"] * profile.frame_bytes,
            "expected_heavy_operations": fixture.expected_heavy_operations,
            "actual_heavy_operations": result["real_heavy_operations"],
            "delivered_results": result["delivered_results"],
            "result_delivery_slots": json.dumps(result_slots),
            "workflow_returned": result["returned"],
            "functional_gate": "PASS" if result["returned"] and result["delivered_results"] == fixture.expected_heavy_operations else "FAIL",
            "dummy_heavy_operations": result["dummy_heavy_operations"],
            "mean_worker_operation_ms": (sum(completed) / len(completed) / 1_000_000) if completed else 0,
            "kernel_accepted_results": sum(bool(row["accepted_result"]) for row in private),
            "cover_response_slots": profile.sessions * profile.slots - result["delivered_results"],
            "interpretation": "DEVELOPMENT_ONLY; profile selected before private execution; no timing-privacy claim",
        })
    with CSV.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    (OUT / "summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    run()

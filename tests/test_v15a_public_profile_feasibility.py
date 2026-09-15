from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_real_slot_denominators_and_fresh_queries() -> None:
    summary = json.loads((ROOT / "V15A_REAL_ACCESS_SLOT_SUMMARY.json").read_text())
    assert summary["microbenchmark_repetitions_per_case"] == 100
    assert {name: value["count"] for name, value in summary["cases"].items()} == {
        "DEPLOYED": 100,
        "UNPROVISIONED": 100,
        "IDLE": 100,
    }
    assert summary["total_slots_executed"] == 800
    assert summary["unique_pir_query_transcripts"] == 800


def test_wire_accounting_is_exactly_branch_independent() -> None:
    rows = list(csv.DictReader((ROOT / "V15A_WIRE_ACCOUNTING.csv").open(newline="")))
    assert [row["case"] for row in rows] == ["DEPLOYED", "UNPROVISIONED", "IDLE"]
    public = [{key: value for key, value in row.items() if key != "case"} for row in rows]
    assert public[0] == public[1] == public[2]
    assert int(public[0]["psi_bytes"]) == 2_277_832
    assert int(public[0]["pir_bytes"]) == 73_568
    assert int(public[0]["bytes_per_public_agent_access_slot"]) == 2_351_400


def test_absolute_scheduler_exposes_capacity_failure() -> None:
    value = json.loads((ROOT / "V15A_SCHEDULER_SUMMARY.json").read_text())
    assert len(value) == 5
    assert all(item["slots"] == 100 for item in value.values())
    assert all(item["scheduled_offsets_identical"] for item in value.values())
    assert min(item["missed_slots"] for item in value.values()) >= 98
    assert min(item["max_queue_depth"] for item in value.values()) >= 51


def test_closure_stops_before_session_scheduler() -> None:
    value = json.loads((ROOT / "V15A_FINAL_CLOSURE.json").read_text())
    assert value["v14_previously_executed_only_logical_slots"] is True
    assert value["current_profile_feasible"] is False
    assert value["profile_redesign_required"] is True
    assert value["full_session_real_psi_pir_schedule"] == "NOT_RUN"
    assert value["full_session_structural_equivalence"] == "NOT_RUN"
    assert value["new_privacy_attack_experiments"] == 0
    assert value["paper_files_modified"] is False


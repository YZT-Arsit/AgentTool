from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_denominators_and_fresh_real_queries() -> None:
    value = json.loads((ROOT / "V15B_PIPELINE_SUMMARY.json").read_text())
    assert value["warm_slots"] == 2500
    assert value["slots_per_mix"] == 500
    assert value["fresh_simplepir_query_transcripts"] == 2501
    assert value["services"]["persistent"] is True
    assert value["services"]["per_slot_process_startup"] is False
    assert value["wire_bytes_per_slot"] == 2_351_400
    rows = list(csv.DictReader((ROOT / "V15B_PIPELINE_BENCHMARK.csv").open(newline="")))
    assert len(rows) == 2501
    assert len({row["pir_query_sha256"] for row in rows}) == len(rows)
    assert {int(row["wire_bytes"]) for row in rows} == {2_351_400}


def test_cadence_stress_is_long_and_selected_delta_has_margin() -> None:
    value = json.loads((ROOT / "V15B_CADENCE_STRESS_SUMMARY.json").read_text())
    assert value["candidates_ms"] == [100, 125, 150, 200, 250, 350]
    assert all(row["slots"] == 1000 for row in value["candidates"].values())
    assert value["candidates"]["100"]["slot_misses"] == 19
    assert value["candidates"]["200"]["slot_misses"] == 1
    selected = value["candidates"]["350"]
    assert selected["slot_misses"] == 0
    assert selected["max_public_queue_depth"] == 0
    assert selected["slot_work_ms"]["max"] < 350
    rows = list(csv.DictReader((ROOT / "V15B_CADENCE_STRESS_RESULTS.csv").open(
        newline="", encoding="utf-8-sig"
    )))
    assert len(rows) == 6000


def test_demand_selection_uses_only_paper_aligned_v14_corpus() -> None:
    rows = list(csv.DictReader((ROOT / "V15B_AGENT_ACCESS_DEMAND.csv").open(newline="")))
    selected = [row for row in rows if row["profile_selection_scope"] == "INCLUDED"]
    assert len(selected) == 8
    assert max(int(row["agent_access_requests_J"]) for row in selected) == 2
    assert max(int(row["agent_access_causal_depth"]) for row in selected) == 2
    assert all(row["evidence_source"] == "V14_E2E_RESULTS.json" for row in selected)
    stale = [row for row in rows if row["profile_selection_scope"] == "STALE_NOT_PROFILE_SELECTING"]
    assert {int(row["agent_access_requests_J"]) for row in stale} == {6}


def test_full_sessions_use_fixed_real_crypto_and_gateway_profiles() -> None:
    value = json.loads((ROOT / "V15B_FULL_SESSION_RESULTS.json").read_text())
    assert value["profile"]["R_A_public_slots"] == 4
    assert value["profile"]["Delta_A_ms"] == 350
    assert value["profile"]["maximum_admitted_agent_requests"] == 3
    assert value["profile"]["guaranteed_serial_causal_depth"] == 2
    assert value["all_semantic_success"] is True
    assert value["full_session_schedule_pass"] is True
    assert value["structural_equivalence"] is True
    assert len(value["sessions"]) == 8
    assert all(row["real_apsi"] and row["real_simplepir"] for row in value["sessions"])
    assert all(row["scheduled_public_slots"] == 4 for row in value["sessions"])
    assert all(row["gateway_public_projection"]["relay_cells"] == 521 for row in value["sessions"])
    assert len({row["public_projection_sha256"] for row in value["sessions"]}) == 1
    structural = json.loads((ROOT / "V15B_STRUCTURAL_EQUIVALENCE.json").read_text())
    assert structural["exact_equality"] is True
    assert structural["timing_indistinguishability_claimed"] is False


def test_closure_and_raw_archive() -> None:
    value = json.loads((ROOT / "V15B_FINAL_CLOSURE.json").read_text())
    assert value["base_v15a_commit"] == "6a04a67b6c54b8a01ca2a38a17247a486e420430"
    assert value["safe_delta_a_ms"] == 350
    assert value["selected_profile"]["R_A_public_slots"] == 4
    assert value["selected_profile"]["total_public_bytes_session"] == 10_384_559
    assert value["gateway_profile_changed"] is False
    assert value["new_privacy_attack_experiments"] == 0
    assert value["paper_files_modified"] is False
    assert value["v15b_decision"] == "PROFILE_REDESIGN_PASS"
    archive = ROOT / "V15B_RAW_TRACES.tar.gz"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == (
        "fbfd8db86c501cab4aac1943948f34c9611ed3514033143e2797e0d260c71763"
    )

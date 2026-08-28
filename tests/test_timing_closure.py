from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results_timing_closure"


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_confirmatory_profiles_were_frozen() -> None:
    frozen = json.loads((RESULTS / "frozen_public_profiles.json").read_text(encoding="utf-8"))
    copied = json.loads((RESULTS / "confirmatory_frozen_configuration.json").read_text(encoding="utf-8"))
    assert frozen == copied
    assert frozen["STANDARD"]["slots"] == 24
    assert frozen["STANDARD"]["frame_bytes"] == 1024
    assert frozen["PIR"] == {"R_pir": 100, "Delta_pir_ms": 5.0}


def test_gateway_host_trace_has_fixed_bidirectional_frames_and_one_destination() -> None:
    rows = _jsonl(RESULTS / "confirmatory_final_single/host_visible_trace.jsonl")
    assert {row["request_bytes"] for row in rows} == {1024}
    assert {row["response_bytes"] for row in rows} == {1024}
    assert {row["destination"] for row in rows} == {"CommonActionGateway"}
    assert len(rows) == 56 * 24
    serialized = json.dumps(rows).lower()
    for forbidden in ('"private_', '"action"', '"provider"', '"operation_id"'):
        assert forbidden not in serialized


def test_noop_cover_does_not_produce_heavy_work_or_effect() -> None:
    folder = RESULTS / "confirmatory_final_single"
    events = _jsonl(folder / "gateway_private_instrumentation.jsonl")
    truth = list(csv.DictReader((folder / "private_ground_truth.csv").open(encoding="utf-8")))
    noop_tokens = {int(row["episode_token"]) for row in truth if row["family"] == "ACTION_TYPE" and row["label"] == "NOOP"}
    assert noop_tokens
    assert not any(int(row["episode_token"]) in noop_tokens and "private_completed_ns" in row for row in events)


def test_real_tool_operations_complete_once_without_dummy_heavy_ops() -> None:
    folder = RESULTS / "confirmatory_final_tool_sequences"
    truth = list(csv.DictReader((folder / "private_ground_truth.csv").open(encoding="utf-8")))
    events = _jsonl(folder / "gateway_private_instrumentation.jsonl")
    requests = [row for row in events if row.get("private_action") == "TOOL"]
    completions = [row for row in events if "private_completed_ns" in row]
    assert len(requests) == len(completions) == 3000
    assert sum(int(row["real_heavy_ops"]) for row in truth) == 3000
    assert all(row["operation_id"] for row in completions)


def test_pir_schedule_runs_real_and_dummy_queries_through_same_server_path() -> None:
    folder = RESULTS / "confirmatory_pir"
    profile = json.loads((folder / "timing_profile.json").read_text(encoding="utf-8"))
    server = _jsonl(folder / "server_visible_trace.jsonl")
    assert profile["real_queries"] == 5706
    assert profile["dummy_queries"] == 894
    assert len(server) == 6600
    assert {row["executor"] for row in server} == {"SimplePIRServer"}
    assert {row["request_kind"] for row in server} == {"PIR_QUERY"}
    assert all(row["scheduled_ns"] and row["request_arrival_ns"] and row["answer_ready_ns"] for row in server)
    visible = (folder / "server_visible_trace.jsonl").read_text(encoding="utf-8").lower()
    assert "private_class" not in visible and "private_index" not in visible


def test_pir_correctness_and_fresh_randomness_remain_intact() -> None:
    metrics = json.loads((RESULTS / "confirmatory_pir/metrics.json").read_text(encoding="utf-8"))
    assert metrics["backend"] == "OFFICIAL_SIMPLEPIR_FULL_PREPROCESSING"
    assert metrics["queries"] == metrics["correct_queries"] == 6600
    assert metrics["fresh_repeated_queries"] is True


def test_nominal_public_deadlines_do_not_depend_on_private_label() -> None:
    rows = _jsonl(RESULTS / "confirmatory_final_single/host_visible_trace.jsonl")
    by_episode = {}
    for row in rows: by_episode.setdefault(row["episode_token"], []).append(row)
    for episode in by_episode.values():
        episode.sort(key=lambda row: row["slot"])
        request_deadlines = [row["cloud_request_scheduled_ns"] for row in episode]
        response_deadlines = [row["gateway_response_scheduled_ns"] for row in episode]
        assert set(b-a for a,b in zip(request_deadlines,request_deadlines[1:])) == {50_000_000}
        assert set(b-a for a,b in zip(response_deadlines,response_deadlines[1:])) == {50_000_000}

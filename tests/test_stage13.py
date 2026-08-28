from __future__ import annotations

import json
import statistics
from pathlib import Path

from stage12_final_p0.workload import load_workload
from stage13_timing_repair.egress import PersistentEgressShaper
from stage13_timing_repair.splits import frozen_split


ROOT = Path(__file__).resolve().parents[1]


def _host_rows(stem: str):
    path = ROOT / "results_stage13" / f"{stem}_final_host.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_stage13_frozen_split_is_12_12_16():
    tasks = load_workload(ROOT / "PUBLIC_DERIVED_WORKLOAD.csv")
    split = frozen_split(tasks)
    assert [*split.values()].count("CALIBRATION") == 12
    assert [*split.values()].count("DEVELOPMENT") == 12
    assert [*split.values()].count("FINAL_TEST") == 16


def test_stage13_host_and_truth_artifacts_are_separate():
    forbidden = ("private_state", "permission_exists", "provenance_exists",
                 "is_dummy", "real_internal", '"branch"', '"family"')
    for stem in ("runtime1", "runtime2"):
        for row in _host_rows(stem):
            encoded = json.dumps(row["host_visible_trace"], sort_keys=True)
            assert not any(field in encoded for field in forbidden)
        assert (ROOT / "results_stage13" / f"{stem}_truth.csv").exists()


def test_stage13_m3_has_fixed_receiver_visible_shape():
    for stem in ("runtime1", "runtime2"):
        rows = [row for row in _host_rows(stem) if row["variant"] == "M3"]
        assert all(len(row["host_visible_trace"]) == 5 for row in rows)
        assert all([event["slot"] for event in row["host_visible_trace"]] == [1,2,3,4,5] for row in rows)
        assert all(event["receiver_bytes"] == 16384 for row in rows for event in row["host_visible_trace"])
        assert all(sum(event["oram_access_count"] for event in row["host_visible_trace"]) == 15 for row in rows)


def test_stage13_receiver_observes_slots_live_not_as_post_epoch_burst():
    for stem in ("runtime1", "runtime2"):
        rows = [row for row in _host_rows(stem) if row["variant"] == "M3"]
        normalized_spans = []
        for row in rows:
            arrivals = [event["arrival_offset_ms"] for event in row["host_visible_trace"]]
            normalized_spans.append((arrivals[-1] - arrivals[0]) / (4 * row["delta_ms"]))
        assert statistics.median(normalized_spans) > 0.9


def test_stage13_dummy_external_effects_are_zero_and_overflow_fails_closed():
    for stem in ("runtime1", "runtime2"):
        for row in _host_rows(stem):
            assert row["dummy_external_effects"] == 0
            if row["overflow"]:
                assert row["effect_count"] == 0
            else:
                assert row["effect_count"] == 1


def test_stage13_egress_commit_gate_is_effect_safe():
    with PersistentEgressShaper() as shaper:
        missing = shaper.start("M3", 5, 2.0, 1024)
        missing.done()
        denied = missing.wait()
        assert denied["final_real"] is False
        assert denied["effect_count"] == 0

        present = shaper.start("M3", 5, 2.0, 1024)
        present.proposal(); present.done()
        allowed = present.wait()
        # Bounded overload may fail closed; it must never create an effect
        # unless the fixed guard admitted the proposal.
        assert allowed["effect_count"] == int(allowed["final_real"])


def test_stage13_fixed_release_deadlines_are_public():
    for stem in ("runtime1", "runtime2"):
        for row in (row for row in _host_rows(stem) if row["variant"] == "M3"):
            assert [event["scheduled_offset_ms"] for event in row["host_visible_trace"]] == [
                row["delta_ms"] * slot for slot in (1,2,3,4,5)
            ]

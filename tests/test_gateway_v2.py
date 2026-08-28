from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway_v2.runner import V2Profile, continuation_sessions, run_gateway_v2


ROOT = Path(__file__).resolve().parents[1]


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_worker_and_pacer_source_have_a_real_process_boundary() -> None:
    worker = (ROOT / "common_action_gateway_v2/worker.go").read_text(encoding="utf-8")
    pacer = (ROOT / "common_action_gateway_v2/pacer.go").read_text(encoding="utf-8")
    assert "net.Conn" not in worker
    assert "WriteFixedFrame" not in worker
    assert "RunProviderEmulator" not in pacer
    assert "adapter.Execute" not in pacer
    assert "completion <- result" in worker
    assert "resultRing.TryPop" in pacer


def test_v2_nominal_schedule_equality_fast_slow_continuation(tmp_path: Path) -> None:
    sessions, providers = continuation_sessions()
    profile = V2Profile(
        name="V2_CONTINUATION_TEST",
        frame_bytes=1024,
        slots=12,
        sessions=2,
        request_delta_ns=50_000_000,
        response_delta_ns=50_000_000,
        mask_ns=10_000_000,
        start_delay_ns=500_000_000,
        inter_session_gap_ns=20_000_000,
    )
    try:
        result = run_gateway_v2(ROOT, tmp_path / "v2", profile, sessions, providers)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 4551:
            pytest.skip("NOT_COMPLETED_ENVIRONMENT: Windows Application Control blocked the local Pacer executable")
        raise
    assert len({result["worker_pid"], result["pacer_pid"], result["client_pid"], *result["provider_pids"]}) == 5

    host = _jsonl(tmp_path / "v2/host_visible_trace.jsonl")
    assert len(host) == 24
    assert {row["request_bytes"] for row in host} == {1024}
    assert {row["response_bytes"] for row in host} == {1024}
    assert {row["destination"] for row in host} == {"CommonActionGatewayV2"}
    assert "provider" not in json.dumps(host).lower()

    by_session: dict[int, list[dict[str, object]]] = {}
    for row in host:
        by_session.setdefault(int(row["session"]), []).append(row)
    for rows in by_session.values():
        rows.sort(key=lambda row: int(row["slot"]))
        deadlines = [int(row["gateway_response_scheduled_ns"]) for row in rows]
        assert [right - left for left, right in zip(deadlines, deadlines[1:])] == [50_000_000] * 11

    delivery = _jsonl(tmp_path / "v2/pacer_private_delivery.jsonl")
    fast = next(row for row in delivery if row.get("operation_id") == "fast-op")
    slow = next(row for row in delivery if row.get("operation_id") == "slow-op")
    assert int(fast["slot"]) <= 2
    assert int(slow["slot"]) <= 8
    assert any(int(row["session"]) == 0 and int(row["slot"]) > int(fast["slot"]) for row in delivery)
    assert any(int(row["session"]) == 1 and int(row["slot"]) > int(slow["slot"]) for row in delivery)

    worker = _jsonl(tmp_path / "v2/worker_private.jsonl")
    effects = [row for row in worker if row.get("effect")]
    summary = next(row for row in worker if row.get("kind") == "SUMMARY")
    assert len(effects) == 2
    assert len({row["operation_id"] for row in effects}) == 2
    assert summary["real_operations"] == 2
    assert summary["dummy_heavy_ops"] == 0


def test_v1_failed_holdout_is_not_a_v2_output() -> None:
    runner = (ROOT / "gateway_v2/runner.py").read_text(encoding="utf-8")
    assert "confirmatory_final" not in runner
    assert "results_timing_closure" not in runner


def test_v2_actual_release_timing_remains_development_only() -> None:
    analysis = json.loads((
        ROOT / "results_gateway_v2/development_stress_windows_frozen_source/development_independence.json"
    ).read_text(encoding="utf-8"))
    assert analysis["kind"] == "DEVELOPMENT_ONLY"
    assert analysis["timing_decision_allowed"] is False
    assert analysis["reference_timing_platform"] is False

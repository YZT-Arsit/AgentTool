from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_v9_final_development_artifacts_are_internally_consistent() -> None:
    freeze = json.loads((ROOT / "V9_STANDARDS_LAYER_FREEZE.json").read_text())
    assert freeze["status"] == "PASS"
    assert freeze["checkpoint"] == "V9_STANDARDS_LAYER_BEFORE_CANONICAL_RUNNER"

    with (ROOT / "CANONICAL_MULTI_AGENT_SMOKE_V9.csv").open() as handle:
        smoke = list(csv.DictReader(handle))
    assert len(smoke) == 4
    assert all(row["passed"] == "True" for row in smoke)
    assert smoke[-1]["authorized"] == "False"
    assert smoke[-1]["provider_invocations"] == "0"

    with (ROOT / "CANONICAL_OHTTP_SIZE_MATRIX_V9.csv").open() as handle:
        sizes = list(csv.DictReader(handle))
    assert len(sizes) == 10
    assert all(row["pass"] == "True" for row in sizes)
    assert {row["ohttp_bytes"] for row in sizes if row["direction"] == "REQUEST"} == {"1079"}
    assert {row["ohttp_bytes"] for row in sizes if row["direction"] == "RESPONSE"} == {"800"}

    summaries = json.loads((ROOT / "results_v9/canonical_runner_development/functional_summary.json").read_text())
    for count in (1, 10, 50, 100):
        row = summaries[str(count)]
        assert row["passed"] is True
        assert row["admitted"] == row["delivered"] == row["provider_invocations"] == count
        assert row["dummy_provider_operations"] == 0
        assert row["profile_overflow_events"] == 0
        assert row["unexpected_duplicate_framework_deliveries"] == 0


def test_canonical_v9_public_relay_events_exclude_private_route_metadata() -> None:
    forbidden_keys = {
        "agent_id", "agent_name", "tool_name", "provider_name", "route_handle",
        "operation_id", "protected_arguments", "authorization", "private_label",
    }
    private_tokens = ("route-tool", "route-agent", "agent-a", "agent-b", "agent-c")
    for path in ROOT.glob("CANONICAL_FUNCTIONAL_*_V9/sessions/*/go_canonical_result.json"):
        result = json.loads(path.read_text())
        assert len(result["public_relay_events"]) == result["rounds"]
        for event in result["public_relay_events"]:
            assert not (set(event) & forbidden_keys)
            serialized = json.dumps(event).lower()
            assert not any(token in serialized for token in private_tokens)
            assert event["request_length"] == 1079
            assert event["response_length"] == 800


def test_canonical_v9_recovery_matrix_preserves_explicit_ambiguity() -> None:
    with (ROOT / "CANONICAL_RECOVERY_MATRIX_V9.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 24
    assert all(row["pass"] == "True" for row in rows)
    partial = [row for row in rows if row["status"] == "PARTIAL"]
    assert len(partial) == 1
    assert partial[0]["crash_point"] == "AFTER_FRAMEWORK_CALLBACK_BEFORE_DURABLE_DELIVERED_STATE"
    unknown_points = {
        "AFTER_DURABLE_PROVIDER_START_BEFORE_CALL",
        "AFTER_PROVIDER_CALL_BEGINS",
        "AFTER_PROVIDER_RESULT_BEFORE_DURABLE_COMMIT",
    }
    unknown = [row for row in rows if row["semantics"] == "NON_IDEMPOTENT_EFFECT" and row["crash_point"] in unknown_points]
    assert len(unknown) == 3
    assert all(row["observed"] == "EFFECT_OUTCOME_UNKNOWN" for row in unknown)

from __future__ import annotations

import base64
import json
from pathlib import Path

from agent_control_virtualization.experiment import compile_frameworks
from agent_control_virtualization.ir import AgentCapsule, ControlEvent, Opcode
from agent_control_virtualization.runtime import AgentControlExecutor, ProtectedEvent
from cryptographic_closure.pir_backend import read_raw_queries


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results_crypto_closure"


def test_real_pir_100k_was_correct_and_fully_preprocessed() -> None:
    metrics = json.loads((RESULTS / "scale_100000/run4/metrics.json").read_text(encoding="utf-8"))
    assert metrics["backend"] == "OFFICIAL_SIMPLEPIR_FULL_PREPROCESSING"
    assert metrics["logical_records"] == 100_000
    assert metrics["logical_bytes"] == 102_400_000
    assert metrics["correct_queries"] == metrics["queries"] == 10
    assert metrics["full_preprocessing_setup_ms"] > 0
    assert metrics["fresh_repeated_queries"] is True


def test_server_trace_excludes_private_labels_and_uses_fresh_queries() -> None:
    folder = RESULTS / "scale_100000/run4"
    visible = (folder / "server_visible_trace.jsonl").read_text(encoding="utf-8").lower()
    for forbidden in ("private_index", "private_class", "agent_name", "logical_agent", "capsule"):
        assert forbidden not in visible
    queries = read_raw_queries(folder / "server_raw_queries.bin")
    assert len(queries) == 10
    assert queries[2] != queries[8]  # index 17 was queried twice
    assert queries[7] != queries[9]  # index 99999 was queried twice


def test_recovered_capsule_feeds_the_common_executor() -> None:
    line = (RESULTS / "scale_100000/run4/client_recovered_records.jsonl").read_text(encoding="utf-8").splitlines()[0]
    capsule = AgentCapsule.deserialize(base64.b64decode(json.loads(line)["record_base64"]))
    executor = AgentControlExecutor({capsule.logical_agent_id: capsule})
    trace = executor.fixed_transcript(capsule.logical_agent_id)
    assert {event["executor"] for event in trace} == {"AgentControlExecutor"}
    assert all(event["actual_request_serialized_bytes"] == 1024 for event in trace)
    assert all("logical_agent_id" not in event and "agent_name" not in event for event in trace)


def test_real_framework_handoff_stays_in_one_physical_executor() -> None:
    for result in compile_frameworks():
        capsules = {capsule.logical_agent_id: capsule for capsule in result.capsules}
        for capsule in result.capsules:
            handoff = next((row for row in capsule.rows if row.opcode == Opcode.HANDOFF), None)
            if handoff is None:
                continue
            executor = AgentControlExecutor(capsules)
            target, transition = executor.step(
                capsule.logical_agent_id,
                handoff.current_state,
                ProtectedEvent(ControlEvent.HANDOFF_REQUEST),
            )
            assert target == transition.target_handle
            assert executor.public_identity == "AgentControlExecutor"
            assert "agent/" not in json.dumps(executor.fixed_transcript(target)).lower()
            return
    raise AssertionError("real-framework fixture did not contain a HANDOFF")


def test_action_structural_and_size_results_are_at_chance() -> None:
    rows = (RESULTS / "tool_action/ACTION_TYPE_ATTACK_RESULTS.csv").read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("STRUCTURAL,") and ",0.25," in line for line in rows[1:])
    assert any(line.startswith("SIZE,") and ",0.25," in line for line in rows[1:])


def test_candidate_code_does_not_use_oram_for_invocation() -> None:
    for folder in (ROOT / "agent_control_virtualization", ROOT / "cryptographic_closure"):
        for path in folder.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            assert "import path_oram" not in text
            assert "import oram" not in text

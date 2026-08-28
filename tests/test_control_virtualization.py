from __future__ import annotations

import struct
from pathlib import Path

from agent_control_virtualization.compiler import compile_workload
from agent_control_virtualization.framework_fixtures import framework_workloads
from agent_control_virtualization.ir import CAPSULE_BYTES, ControlEvent, Opcode
from agent_control_virtualization.lookup import MockPrivateLookup
from agent_control_virtualization.runtime import (
    AgentControlExecutor, ProtectedEvent, serialize_fixed_envelope, structural_signature,
)


def _compiled():
    return [compile_workload(workload, 1000 + index * 100) for index, workload in enumerate(framework_workloads())]


def test_real_framework_objects_compile_with_explicit_coverage() -> None:
    results = _compiled()
    assert {result.framework for result in results} == {"OpenAI Agents SDK", "Microsoft Agent Framework"}
    total = sum(result.total for result in results)
    covered = sum(result.compiled + result.shared for result in results)
    assert covered / total >= 0.80
    assert any(result.unsupported for result in results)


def test_capsules_have_fixed_width_and_distinct_mock_registry_ids() -> None:
    capsule = _compiled()[0].capsules[0]
    serialized = capsule.serialize()
    assert len(serialized) == CAPSULE_BYTES
    lookup = MockPrivateLookup(1000, (serialized,))
    first = lookup.lookup(0)
    last = lookup.lookup(999)
    assert len(first) == len(last) == CAPSULE_BYTES
    assert struct.unpack_from("!I", first, 8)[0] == 0
    assert struct.unpack_from("!I", last, 8)[0] == 999
    assert lookup.security_status == "MOCK_PRIVATE_LOOKUP_NON_CRYPTOGRAPHIC"
    recovered = type(capsule).deserialize(serialized)
    assert recovered.logical_agent_id == capsule.logical_agent_id
    assert recovered.rows[0].opcode == capsule.rows[0].opcode


def test_common_executor_trace_contains_no_logical_agent_or_named_endpoint() -> None:
    results = _compiled()
    capsules = {capsule.logical_agent_id: capsule for result in results for capsule in result.capsules}
    executor = AgentControlExecutor(capsules)
    traces = [executor.fixed_transcript(agent_id) for agent_id in (1, 17, 99999)]
    assert len({structural_signature(trace) for trace in traces}) == 1
    serialized = structural_signature(traces[0])
    for forbidden in ("logical_agent_id", "WeatherExecutor", "LegalExecutor", "DataExecutor"):
        assert forbidden not in serialized
    assert all(event["executor"] == "AgentControlExecutor" for event in traces[0])
    assert len(serialize_fixed_envelope(1, 1024)) == 1024


def test_handoff_is_a_logical_transition_through_same_executor() -> None:
    result = next(result for result in _compiled() if any(c.handoff_count for c in result.capsules))
    capsule = next(c for c in result.capsules if c.handoff_count)
    row = next(row for row in capsule.rows if row.opcode == Opcode.HANDOFF)
    executor = AgentControlExecutor({c.logical_agent_id: c for c in result.capsules})
    target, transition = executor.step(
        capsule.logical_agent_id, row.current_state, ProtectedEvent(ControlEvent.HANDOFF_REQUEST)
    )
    assert transition.opcode == Opcode.HANDOFF
    assert target == row.target_handle
    assert target != capsule.logical_agent_id
    assert executor.public_identity == "AgentControlExecutor"
    assert str(target) not in structural_signature(executor.fixed_transcript(target))


def test_cover_slots_never_execute_dummy_heavy_work() -> None:
    capsule = _compiled()[0].capsules[0]
    executor = AgentControlExecutor({capsule.logical_agent_id: capsule})
    counters, trace, _ = executor.execute_one_heavy(capsule.logical_agent_id)
    assert counters.real_heavy_ops == 1
    assert counters.dummy_heavy_ops == 0
    assert counters.fixed_frames == len(trace) == 4


def test_mock_lookup_does_not_claim_target_privacy() -> None:
    capsule = _compiled()[0].capsules[0]
    lookup = MockPrivateLookup(10, (capsule.serialize(),))
    measured = lookup.lookup_measured(7)
    assert measured.host_visible_index == 7
    assert lookup.public_metrics()["cryptographic_privacy"] is False


def test_rejected_oram_invocation_path_is_absent() -> None:
    root = Path(__file__).resolve().parents[1]
    rejected = [
        root / "stage11_core_redesign" / "routing.py",
        root / "stage11_core_redesign" / "experiment.py",
        root / "scripts" / "run_stage11.py",
        root / "results_stage11" / "routing_privacy.csv",
        root / "results_stage12" / "private_dispatch.csv",
    ]
    assert not any(path.exists() for path in rejected)
    active_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "agent_control_virtualization").glob("*.py")
    ).lower()
    assert "path_oram" not in active_source
    retained = (root / "src" / "path_oram.py").read_text(encoding="utf-8")
    assert "OPTIONAL_PRIVATE_STATE_BACKEND" in retained

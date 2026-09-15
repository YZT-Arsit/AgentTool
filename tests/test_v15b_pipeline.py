from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from v14_provisioned_agents.artifact import PIR_RECORD_BYTES, ProvisionedAgentArtifactCodec
from v14_provisioned_agents.fixtures import STORE_EPOCH, make_artifact
from v14_provisioned_agents.models import AgentFramework, PIRRowHandle
from v14_provisioned_agents.psi import APSIResult, APSIWireMetrics
from v14_provisioned_agents.simplepir import SimplePIRResult
from v15b_agent_access.pipeline import (
    AgentAccessProfile,
    AgentAccessRequest,
    PipelinedAgentAccessScheduler,
    ProfileCapacityExceeded,
)


WIRE = APSIWireMetrics(104, 104, 697972, 1579652, 1, 2, 3, 4)
DUMMY = 100000


class PSI:
    def __init__(self, rows): self.rows = rows; self.queries = []
    def query(self, agent_id):
        self.queries.append(agent_id)
        row = self.rows.get(agent_id)
        return APSIResult(None if row is None else PIRRowHandle(row, STORE_EPOCH), WIRE)


class PIR:
    def __init__(self, rows): self.rows = rows; self.queries = []
    def query(self, operation_id, row_index):
        self.queries.append((operation_id, row_index))
        value = self.rows.get(row_index, b"\0" * PIR_RECORD_BYTES)
        return SimplePIRResult(value, 36388, 37180, hashlib.sha256(operation_id.encode()).hexdigest(), True)


def scheduler(requests=2):
    codec = ProvisionedAgentArtifactCodec(b"k" * 32, STORE_EPOCH)
    artifact = make_artifact(101, AgentFramework.OPENAI_AGENTS_SDK, role="test")
    psi, pir, gateway = PSI({101: 17}), PIR({17: codec.encode(artifact)}), []
    value = PipelinedAgentAccessScheduler(
        AgentAccessProfile("V15B-TEST", requests, 200), psi, pir, codec,
        dummy_row=DUMMY, gateway_queue=gateway.append, production=False,
    )
    return value, psi, pir, gateway


def test_fixed_one_slot_offset_and_parallel_public_shape() -> None:
    value, psi, pir, gateway = scheduler(2)
    value.enqueue(AgentAccessRequest("a", 101))
    value.execute_slot()
    assert value.results == []
    value.execute_slot()
    assert value.results[0].request.request_id == "a"
    assert value.results[0].admitted_slot == 0 and value.results[0].ready_slot == 1
    value.execute_slot(drain=True)
    assert psi.queries == [101, None, None]
    assert [row for _, row in pir.queries] == [DUMMY, 17, DUMMY]
    assert gateway == []
    assert len(value.public_slots) == 3
    assert len({tuple(slot.canonical().keys()) for slot in value.public_slots}) == 1


def test_miss_is_dummy_pir_and_queues_gateway_without_new_public_slot() -> None:
    value, psi, pir, gateway = scheduler(1)
    value.enqueue(AgentAccessRequest("miss", 1_000_101))
    value.execute_slot(); value.execute_slot(drain=True)
    assert psi.queries == [1_000_101, None]
    assert [row for _, row in pir.queries] == [DUMMY, DUMMY]
    assert gateway == [1_000_101]
    assert value.results[0].gateway_repository_queued is True


def test_capacity_is_fail_closed_and_schedule_does_not_extend() -> None:
    value, *_ = scheduler(1)
    value.enqueue(AgentAccessRequest("a", 101))
    with pytest.raises(ProfileCapacityExceeded, match="PROFILE_AGENT_ACCESS_CAPACITY_EXCEEDED"):
        value.enqueue(AgentAccessRequest("b", 102))
    value.execute_slot(); value.execute_slot(drain=True)
    with pytest.raises(RuntimeError, match="closed"):
        value.execute_slot()


def test_public_projection_omits_private_state() -> None:
    hit, *_ = scheduler(1); hit.enqueue(AgentAccessRequest("hit", 101))
    hit.execute_slot(); hit.execute_slot(drain=True)
    miss, *_ = scheduler(1); miss.enqueue(AgentAccessRequest("miss", 1_000_101))
    miss.execute_slot(); miss.execute_slot(drain=True)
    idle, *_ = scheduler(1); idle.execute_slot(); idle.execute_slot(drain=True)
    assert [x.canonical() for x in hit.public_slots] == [x.canonical() for x in miss.public_slots]
    assert [x.canonical() for x in hit.public_slots] == [x.canonical() for x in idle.public_slots]
    forbidden = ("agent_id", "row", "match", "dummy", "source")
    assert not any(word in str(hit.public_slots[0].canonical()).lower() for word in forbidden)


def test_profile_reports_bounded_serial_depth() -> None:
    # The public R_A reported for this profile is four: three admission slots
    # plus the mandatory one-slot drain.
    profile = AgentAccessProfile("P2", 3, 200).validate()
    assert profile.total_public_slots == 4
    assert profile.guaranteed_serial_causal_depth == 2
    assert profile.public_horizon_ms == 825


def test_production_scheduler_rejects_mock_crypto() -> None:
    codec = ProvisionedAgentArtifactCodec(b"k" * 32, STORE_EPOCH)
    with pytest.raises(Exception, match="REAL_PSI_REQUIRED"):
        PipelinedAgentAccessScheduler(
            AgentAccessProfile("PRODUCTION", 1, 200), PSI({}), PIR({}), codec,
            dummy_row=DUMMY,
        )


def test_fixed_schedule_is_ordinal_based_not_completion_chained() -> None:
    value, *_ = scheduler(2)
    now = [1_000_000_000]
    def clock(): return now[0]
    def sleep(seconds): now[0] += round(seconds * 1e9)
    rows = value.run_fixed_schedule(clock_ns=clock, sleep=sleep)
    scheduled = [row["scheduled_time_ns"] for row in rows]
    assert scheduled == [1_025_000_000, 1_225_000_000, 1_425_000_000]
    assert all(row["start_lateness_ms"] == 0 for row in rows)

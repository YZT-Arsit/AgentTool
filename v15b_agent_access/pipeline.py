from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import time
from typing import Callable, Protocol

from v14_provisioned_agents.artifact import ProvisionedAgentArtifactCodec
from v14_provisioned_agents.models import PIRRowHandle, ProvisionedAgentArtifactV1, validate_agent_id
from v14_provisioned_agents.psi import APSIResult, require_real_apsi
from v14_provisioned_agents.simplepir import SimplePIRResult, require_real_simplepir


class PSIClient(Protocol):
    def query(self, agent_id: int | None) -> APSIResult: ...


class PIRClient(Protocol):
    def query(self, operation_id: str, row_index: int) -> SimplePIRResult: ...


class ProfileCapacityExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentAccessProfile:
    """Public Gamma_A profile.

    ``real_admission_slots`` counts public opportunities at which a queued
    request may enter the PSI stage.  One additional public drain slot is
    always emitted so the final PSI result receives its corresponding PIR.
    """

    profile_id: str
    real_admission_slots: int
    interval_ms: int
    initial_lead_ms: int = 25

    def validate(self) -> "AgentAccessProfile":
        if not self.profile_id:
            raise ValueError("empty Agent-access profile identifier")
        if self.real_admission_slots < 1 or self.interval_ms < 1 or self.initial_lead_ms < 0:
            raise ValueError("invalid Agent-access profile")
        return self

    @property
    def total_public_slots(self) -> int:
        return self.real_admission_slots + 1

    @property
    def public_horizon_ms(self) -> int:
        return self.initial_lead_ms + self.total_public_slots * self.interval_ms

    @property
    def guaranteed_serial_causal_depth(self) -> int:
        # A dependent request is learned only after the parent's PIR stage.
        return self.total_public_slots // 2


@dataclass(frozen=True)
class AgentAccessRequest:
    request_id: str
    agent_id: int

    def validate(self) -> "AgentAccessRequest":
        if not self.request_id:
            raise ValueError("empty Agent-access request identifier")
        validate_agent_id(self.agent_id)
        return self


@dataclass(frozen=True)
class _PipelineRegister:
    request: AgentAccessRequest | None
    row_handle: PIRRowHandle | None


@dataclass(frozen=True)
class AgentAccessResult:
    request: AgentAccessRequest
    provisioned: bool
    artifact: ProvisionedAgentArtifactV1 | None
    gateway_repository_queued: bool
    admitted_slot: int
    ready_slot: int


@dataclass(frozen=True)
class PublicSlotProjection:
    slot: int
    profile_id: str
    psi_public_endpoint: str
    psi_messages: int
    psi_framed_lengths: tuple[int, int, int, int]
    pir_public_endpoint: str
    pir_messages: int
    pir_framed_lengths: tuple[int, int]
    gateway_public_endpoint: str
    gateway_frame_count: int
    gateway_directions: tuple[str, str]
    gateway_frame_lengths: tuple[int, int]

    def canonical(self) -> dict[str, object]:
        return {
            "slot": self.slot,
            "profile_id": self.profile_id,
            "psi_public_endpoint": self.psi_public_endpoint,
            "psi_messages": self.psi_messages,
            "psi_framed_lengths": list(self.psi_framed_lengths),
            "pir_public_endpoint": self.pir_public_endpoint,
            "pir_messages": self.pir_messages,
            "pir_framed_lengths": list(self.pir_framed_lengths),
            "gateway_public_endpoint": self.gateway_public_endpoint,
            "gateway_frame_count": self.gateway_frame_count,
            "gateway_directions": list(self.gateway_directions),
            "gateway_frame_lengths": list(self.gateway_frame_lengths),
        }


class PipelinedAgentAccessScheduler:
    """Trusted FIFO scheduler with a fixed one-public-slot PSI/PIR offset."""

    def __init__(
        self,
        profile: AgentAccessProfile,
        psi: PSIClient,
        pir: PIRClient,
        codec: ProvisionedAgentArtifactCodec,
        *,
        dummy_row: int,
        gateway_queue: Callable[[int], None] | None = None,
        gateway_endpoint: str = "TRUSTED_GATEWAY",
        gateway_cells: int = 521,
        gateway_request_bytes: int = 1079,
        gateway_response_bytes: int = 800,
        production: bool = True,
    ):
        if production:
            require_real_apsi(psi)
            require_real_simplepir(pir)
        self.profile = profile.validate()
        self.psi, self.pir, self.codec = psi, pir, codec
        self.dummy_row = dummy_row
        self.gateway_queue = gateway_queue or (lambda _agent_id: None)
        self.gateway_endpoint = gateway_endpoint
        self.gateway_cells = gateway_cells
        self.gateway_request_bytes = gateway_request_bytes
        self.gateway_response_bytes = gateway_response_bytes
        self._queue: deque[AgentAccessRequest] = deque()
        self._register = _PipelineRegister(None, None)
        self._admitted_slots: dict[str, int] = {}
        self._slot = 0
        self._closed = False
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="v15b-crypto")
        self.results: list[AgentAccessResult] = []
        self.public_slots: list[PublicSlotProjection] = []

    def enqueue(self, request: AgentAccessRequest) -> None:
        if self._closed:
            raise RuntimeError("Agent-access session is closed")
        request.validate()
        if len(self._queue) + len(self._admitted_slots) >= self.profile.real_admission_slots:
            raise ProfileCapacityExceeded("PROFILE_AGENT_ACCESS_CAPACITY_EXCEEDED")
        if request.request_id in self._admitted_slots or any(
            value.request_id == request.request_id for value in self._queue
        ):
            raise ValueError("duplicate Agent-access request identifier")
        self._queue.append(request)

    def _finalize_previous(self, pir: SimplePIRResult, slot: int) -> AgentAccessResult | None:
        previous = self._register
        if previous.request is None:
            return None
        admitted = self._admitted_slots[previous.request.request_id]
        if previous.row_handle is None:
            self.gateway_queue(previous.request.agent_id)
            result = AgentAccessResult(
                previous.request, False, None, True, admitted, slot
            )
        else:
            if previous.row_handle.row_index == self.dummy_row:
                raise RuntimeError("real provisioned Agent resolved to the dummy PIR row")
            if previous.row_handle.store_epoch != self.codec.store_epoch:
                raise RuntimeError("stale PSI PIR-row handle")
            artifact = self.codec.decode(pir.row, previous.request.agent_id)
            result = AgentAccessResult(
                previous.request, True, artifact, False, admitted, slot
            )
        self.results.append(result)
        return result

    def execute_slot(self, *, drain: bool = False) -> AgentAccessResult | None:
        if self._closed:
            raise RuntimeError("Agent-access session is closed")
        if self._slot >= self.profile.total_public_slots:
            raise RuntimeError("fixed Agent-access schedule is exhausted")
        if drain and self._slot != self.profile.total_public_slots - 1:
            raise ValueError("drain is permitted only in the final public slot")
        if self._slot == self.profile.total_public_slots - 1 and not drain:
            raise ValueError("final public slot must be an explicit drain")

        current = None if drain else (self._queue.popleft() if self._queue else None)
        if current is not None:
            self._admitted_slots[current.request_id] = self._slot
        previous_row = (
            self._register.row_handle.row_index
            if self._register.row_handle is not None
            else self.dummy_row
        )
        psi_future = self._executor.submit(self.psi.query, None if current is None else current.agent_id)
        pir_future = self._executor.submit(
            self.pir.query, f"v15b-agent-access-{self._slot:04d}", previous_row
        )
        psi = psi_future.result()
        pir = pir_future.result()
        completed = self._finalize_previous(pir, self._slot)
        self._register = _PipelineRegister(current, psi.row_handle)
        self.public_slots.append(
            PublicSlotProjection(
                slot=self._slot,
                profile_id=self.profile.profile_id,
                psi_public_endpoint="ENTERPRISE_AGENT_STORE_PSI",
                psi_messages=4,
                psi_framed_lengths=(
                    psi.wire.oprf_request_bytes,
                    psi.wire.oprf_response_bytes,
                    psi.wire.query_request_bytes,
                    psi.wire.query_response_bytes,
                ),
                pir_public_endpoint="ENTERPRISE_AGENT_STORE_PIR",
                pir_messages=2,
                pir_framed_lengths=(pir.query_bytes, pir.answer_bytes),
                gateway_public_endpoint=self.gateway_endpoint,
                gateway_frame_count=self.gateway_cells,
                gateway_directions=("TEE_TO_GATEWAY", "GATEWAY_TO_TEE"),
                gateway_frame_lengths=(self.gateway_request_bytes, self.gateway_response_bytes),
            )
        )
        self._slot += 1
        if drain:
            self._closed = True
            self._executor.shutdown(wait=True)
            if self._queue:
                raise ProfileCapacityExceeded("PROFILE_AGENT_ACCESS_CAPACITY_EXCEEDED")
            if self._register.request is not None:
                raise RuntimeError("drain slot admitted an unexpected request")
        return completed

    def close(self) -> None:
        if not self._closed:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._closed = True

    def run_fixed_schedule(
        self,
        *,
        on_result: Callable[[AgentAccessResult], None] | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
        sleep: Callable[[float], None] = time.sleep,
    ) -> list[dict[str, int | float]]:
        """Execute the complete absolute public schedule, including drain.

        The next timestamp is derived from the public origin and ordinal, never
        from completion of the prior cryptographic work.
        """
        origin = clock_ns() + self.profile.initial_lead_ms * 1_000_000
        diagnostics: list[dict[str, int | float]] = []
        for slot in range(self.profile.total_public_slots):
            scheduled = origin + slot * self.profile.interval_ms * 1_000_000
            now = clock_ns()
            if now < scheduled:
                sleep((scheduled - now) / 1e9)
            actual = clock_ns()
            result = self.execute_slot(drain=slot == self.profile.total_public_slots - 1)
            completed = clock_ns()
            if result is not None and on_result is not None:
                on_result(result)
            diagnostics.append({
                "slot": slot,
                "scheduled_time_ns": scheduled,
                "actual_start_ns": actual,
                "completed_ns": completed,
                "start_lateness_ms": max(0, actual - scheduled) / 1e6,
                "completion_after_next_deadline_ms": max(
                    0, completed - (scheduled + self.profile.interval_ms * 1_000_000)
                ) / 1e6,
            })
        return diagnostics

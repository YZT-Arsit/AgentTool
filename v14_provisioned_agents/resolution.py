from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .artifact import ProvisionedAgentArtifactCodec
from .loader import AgentLoader, LoadedFrameworkAgent
from .models import ProvisionedAgentArtifactV1, validate_agent_id
from .psi import APSIResult, RealLabeledAPSIClient, require_real_apsi
from .simplepir import PersistentSimplePIRArtifactClient, SimplePIRResult, require_real_simplepir


class ResolutionKind(StrEnum):
    PROVISIONED = "PROVISIONED"
    UNPROVISIONED = "UNPROVISIONED"
    IDLE = "IDLE"


class InternetArtifactGateway(Protocol):
    def retrieve_artifact(self, agent_id: int) -> bytes: ...

    def public_profile(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class AgentAccessPublicStructure:
    psi_slots: int
    psi_receiver_items: int
    psi_request_bytes: int
    psi_response_bytes: int
    pir_slots: int
    pir_query_bytes: int
    pir_answer_bytes: int
    gateway_profile: dict[str, object]

    def canonical(self) -> dict[str, object]:
        return {
            "psi_slots": self.psi_slots,
            "psi_receiver_items": self.psi_receiver_items,
            "psi_request_bytes": self.psi_request_bytes,
            "psi_response_bytes": self.psi_response_bytes,
            "pir_slots": self.pir_slots,
            "pir_query_bytes": self.pir_query_bytes,
            "pir_answer_bytes": self.pir_answer_bytes,
            "gateway_profile": self.gateway_profile,
        }


@dataclass(frozen=True)
class AgentResolution:
    kind: ResolutionKind
    requested_agent_id: int | None
    artifact: ProvisionedAgentArtifactV1 | None
    loaded: LoadedFrameworkAgent | None
    psi: APSIResult
    pir: SimplePIRResult
    public: AgentAccessPublicStructure
    gateway_repository_retrieval: bool
    nested_resolutions: tuple["AgentResolution", ...] = ()


class PaperAlignedAgentResolver:
    """Singleton PSI + fixed PIR + trusted artifact decode/load composition."""

    def __init__(
        self,
        psi: RealLabeledAPSIClient,
        pir: PersistentSimplePIRArtifactClient,
        codec: ProvisionedAgentArtifactCodec,
        loader: AgentLoader,
        gateway: InternetArtifactGateway,
        *,
        dummy_row: int,
        production: bool = True,
    ):
        if production:
            require_real_apsi(psi)
            require_real_simplepir(pir)
        if not 0 <= dummy_row < pir.record_count:
            raise ValueError("dummy PIR row is outside database")
        self.psi, self.pir, self.codec = psi, pir, codec
        self.loader, self.gateway, self.dummy_row = loader, gateway, dummy_row
        self._active: set[int] = set()
        self.resolution_count = 0
        self.remote_provisioned_agent_executions = 0
        self.agent_specific_gateway_destinations = 0

    def _public(self, psi: APSIResult, pir: SimplePIRResult) -> AgentAccessPublicStructure:
        return AgentAccessPublicStructure(
            psi_slots=1,
            psi_receiver_items=1,
            psi_request_bytes=psi.wire.request_bytes,
            psi_response_bytes=psi.wire.response_bytes,
            pir_slots=1,
            pir_query_bytes=pir.query_bytes,
            pir_answer_bytes=pir.answer_bytes,
            gateway_profile=self.gateway.public_profile(),
        )

    def resolve(self, agent_id: int | None) -> AgentResolution:
        if agent_id is not None:
            validate_agent_id(agent_id)
            if agent_id in self._active:
                raise RuntimeError("cyclic Agent-to-Agent reference")
        self.resolution_count += 1
        operation_id = f"v14-agent-access-{self.resolution_count:04d}"
        psi = self.psi.query(agent_id)
        if agent_id is None:
            pir = self.pir.query(operation_id, self.dummy_row)
            return AgentResolution(
                ResolutionKind.IDLE, None, None, None, psi, pir, self._public(psi, pir), False
            )

        if psi.row_handle is not None:
            handle = psi.row_handle
            if handle.store_epoch != self.codec.store_epoch or handle.record_version != 1:
                raise RuntimeError("APSI row handle is stale or incompatible")
            if handle.row_index == self.dummy_row:
                raise RuntimeError("real Agent maps to reserved dummy row")
            pir = self.pir.query(operation_id, handle.row_index)
            artifact = self.codec.decode(pir.row, agent_id)
            kind = ResolutionKind.PROVISIONED
            gateway_retrieval = False
        else:
            pir = self.pir.query(operation_id, self.dummy_row)
            row = self.gateway.retrieve_artifact(agent_id)
            artifact = self.codec.decode(row, agent_id)
            kind = ResolutionKind.UNPROVISIONED
            gateway_retrieval = True

        self._active.add(agent_id)
        try:
            nested = tuple(self.resolve(child_id) for child_id in artifact.sub_agent_ids)
            children = tuple(value.loaded for value in nested)
            if any(child is None for child in children):
                raise RuntimeError("nested Agent resolution returned no loadable Agent")
            loaded = self.loader.load(artifact, children)  # type: ignore[arg-type]
        finally:
            self._active.remove(agent_id)
        return AgentResolution(
            kind,
            agent_id,
            artifact,
            loaded,
            psi,
            pir,
            self._public(psi, pir),
            gateway_retrieval,
            nested,
        )

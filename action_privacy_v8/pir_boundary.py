from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PreparedPIRQuery:
    opaque_query_bytes: bytes
    private_recovery_context: object


class TrustedPIRClient(Protocol):
    """Trusted-side SimplePIR semantics.

    The private Agent ID, hints/client state, randomness, and recovery context
    never enter the server interface.
    """

    def prepare_query(self, agent_id: int) -> PreparedPIRQuery: ...
    def recover(self, context: object, opaque_answer_bytes: bytes) -> bytes: ...


class UntrustedPIRServer(Protocol):
    """Untrusted server accepts only serialized query bytes."""

    def answer(self, opaque_query_bytes: bytes) -> bytes: ...


FORBIDDEN_SERVER_LOG_FIELDS = frozenset(
    {"private_index", "private_class", "agent_id", "agent_name", "route_handle", "descriptor_digest"}
)


def audit_server_log(serialized_log: str) -> None:
    lowered = serialized_log.lower()
    leaked = sorted(field for field in FORBIDDEN_SERVER_LOG_FIELDS if field in lowered)
    if leaked:
        raise AssertionError(f"private PIR client field entered server log: {leaked}")


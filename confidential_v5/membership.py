from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Protocol


def capability_token(normalized_capability: str, domain_key: bytes) -> bytes:
    if not normalized_capability or normalized_capability != normalized_capability.strip().lower():
        raise ValueError("capability must be normalized lower-case text")
    return hashlib.blake2s(normalized_capability.encode("utf-8"), key=domain_key,
                           digest_size=32).digest()


@dataclass(frozen=True)
class MembershipResult:
    found: bool
    private_agent_index: int | None
    backend: str
    cryptographic_privacy: str


class MembershipBackend(Protocol):
    def lookup(self, token: bytes) -> MembershipResult: ...


class LocalTrustedCatalog:
    """Catalog wholly resident inside the confidential runtime; PSI unnecessary."""

    backend = "LOCAL_TEE_MEMBERSHIP"

    def __init__(self, rows: Mapping[bytes, int]):
        self._rows = dict(rows)

    def lookup(self, token: bytes) -> MembershipResult:
        index = self._rows.get(token)
        return MembershipResult(index is not None, index, self.backend,
                                "NOT_APPLICABLE_CATALOG_INSIDE_TEE")


class IdealPrivateMembershipReference:
    """Non-cryptographic interface test double for an outsourced catalog.

    It must never be used as evidence that an untrusted registry cannot learn
    the query.  It exists only to lock the client/server API until an audited
    offline PSI/OPRF implementation is available.
    """

    backend = "IDEAL_REFERENCE_NON_CRYPTOGRAPHIC"

    def __init__(self, rows: Mapping[bytes, int]):
        self._rows = dict(rows)

    def lookup(self, token: bytes) -> MembershipResult:
        index = self._rows.get(token)
        return MembershipResult(index is not None, index, self.backend,
                                "CRYPTOGRAPHIC_PSI_NOT_IMPLEMENTED")

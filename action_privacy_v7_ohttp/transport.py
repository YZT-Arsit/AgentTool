from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class CanonicalTransportUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OHTTPKeyConfiguration:
    key_id: int
    kem_id: int
    kdf_id: int
    aead_id: int
    public_key: bytes
    rotation_epoch: int
    authenticated_source: str


class OHTTPClientBackend(Protocol):
    """RFC 9458 client contract; no implementation is bundled offline."""

    backend_name: str
    rfc9458_wire: bool

    def encapsulate_request(self, bhttp_request: bytes) -> tuple[bytes, object]: ...
    def decapsulate_response(self, context: object, encapsulated_response: bytes) -> bytes: ...


class KnownLengthBHTTPCodec(Protocol):
    """RFC 9292 known-length codec contract; intentionally unimplemented."""

    def encode_request(self, semantic_target: str, private_message: object, padded_bytes: int) -> bytes: ...
    def decode_request(self, encoded: bytes) -> tuple[str, object]: ...
    def encode_response(self, private_message: object, padded_bytes: int) -> bytes: ...
    def decode_response(self, encoded: bytes) -> object: ...


class RFC9458BackendUnavailable:
    backend_name = "RFC9458_OHTTP_NOT_IMPLEMENTED_OFFLINE"
    rfc9458_wire = False

    def encapsulate_request(self, bhttp_request: bytes) -> tuple[bytes, object]:
        raise CanonicalTransportUnavailable(
            "No audited RFC 9458 plus RFC 9292 dependency exists in the offline cache"
        )

    def decapsulate_response(self, context: object, encapsulated_response: bytes) -> bytes:
        raise CanonicalTransportUnavailable(
            "No RFC 9458 response context is available"
        )


@dataclass(frozen=True)
class LegacyDevTransportMarker:
    """Classification marker for the frozen custom AES-GCM development wire."""

    backend_name: str = "LEGACY_DEV_TRANSPORT"
    rfc9458_wire: bool = False
    canonical: bool = False

    def require_canonical(self) -> None:
        raise CanonicalTransportUnavailable(
            "LEGACY_DEV_TRANSPORT is not RFC 9458 and cannot satisfy the V7-OHTTP gate"
        )

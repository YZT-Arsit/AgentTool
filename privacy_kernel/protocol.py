from __future__ import annotations

import hashlib
import os
import struct
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


PROTOCOL_VERSION = 3
DIRECTION_REQUEST = 1
DIRECTION_RESPONSE = 2
PUBLIC_HEADER = struct.Struct("!HBBIIQ")
NONCE_BYTES = 12
TAG_BYTES = 16
OPERATION_ID_BYTES = 32
RESULT_PAYLOAD_BYTES = 720

ACTION_NOOP = 0
ACTION_TOOL = 1
ACTION_LLM = 2
ACTION_AGENT = 3

STATUS_WAIT = 0
STATUS_OK = 1
STATUS_ERROR = 2
STATUS_TIMEOUT = 3
STATUS_CANCELLED = 4
STATUS_AMBIGUOUS = 5


@dataclass(frozen=True)
class CanonicalProfile:
    name: str
    frame_bytes: int
    slots: int
    sessions: int
    request_delta_ns: int
    response_delta_ns: int
    mask_ns: int
    start_delay_ns: int
    inter_session_gap_ns: int

    @property
    def profile_id(self) -> int:
        material = "|".join(str(value) for value in (
            self.name, self.frame_bytes, self.slots, self.sessions,
            self.request_delta_ns, self.response_delta_ns, self.mask_ns,
            self.start_delay_ns, self.inter_session_gap_ns,
        ))
        return int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:8], "big")

    @property
    def session_span_ns(self) -> int:
        return max(self.slots * self.request_delta_ns, self.slots * self.response_delta_ns) + self.inter_session_gap_ns

    def as_public_dict(self) -> dict[str, int | str]:
        return {
            "name": self.name, "frame_bytes": self.frame_bytes, "slots": self.slots,
            "sessions": self.sessions, "request_delta_ns": self.request_delta_ns,
            "response_delta_ns": self.response_delta_ns, "mask_ns": self.mask_ns,
            "start_delay_ns": self.start_delay_ns, "inter_session_gap_ns": self.inter_session_gap_ns,
        }


@dataclass(frozen=True)
class PublicHeader:
    version: int
    direction: int
    session: int
    slot: int
    profile_id: int


@dataclass(frozen=True)
class DecodedResult:
    status: int
    operation_id: str
    payload: bytes
    session: int
    slot: int


def write_restricted_key(path: Path, key: bytes) -> None:
    if len(key) not in (16, 24, 32):
        raise ValueError("AES key must be 16, 24, or 32 bytes")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, key.hex().encode("ascii"))
    finally:
        os.close(descriptor)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def parse_public_header(frame: bytes) -> PublicHeader:
    if len(frame) < PUBLIC_HEADER.size + NONCE_BYTES + TAG_BYTES:
        raise ValueError("short frame")
    version, direction, reserved, session, slot, profile_id = PUBLIC_HEADER.unpack_from(frame)
    if version != PROTOCOL_VERSION or reserved != 0:
        raise ValueError("invalid protocol header")
    if direction not in (DIRECTION_REQUEST, DIRECTION_RESPONSE):
        raise ValueError("invalid direction")
    return PublicHeader(version, direction, session, slot, profile_id)


class EnvelopeCodec:
    """Trusted-only fixed-frame encoder and response consumer."""

    def __init__(self, key: bytes, profile: CanonicalProfile):
        self._aead = AESGCM(key)
        self.profile = profile
        self._response_next = 0

    def _header(self, direction: int, session: int, slot: int) -> bytes:
        return PUBLIC_HEADER.pack(PROTOCOL_VERSION, direction, 0, session, slot, self.profile.profile_id)

    @staticmethod
    def _operation_id(value: str) -> bytes:
        encoded = value.encode("utf-8")
        if len(encoded) > OPERATION_ID_BYTES:
            raise ValueError("operation ID exceeds fixed field")
        return encoded.ljust(OPERATION_ID_BYTES, b"\0")

    def encode_request(self, session: int, slot: int, *, action: int, provider: int,
                       operation_id: str, payload: bytes = b"") -> bytes:
        plain_bytes = self.profile.frame_bytes - PUBLIC_HEADER.size - NONCE_BYTES - TAG_BYTES
        if len(payload) > plain_bytes - 36:
            raise ValueError("request payload exceeds public frame bound")
        plain = bytearray(plain_bytes)
        plain[0] = action
        plain[1] = provider
        struct.pack_into("!H", plain, 2, len(payload))
        plain[4:36] = self._operation_id(operation_id)
        plain[36:36 + len(payload)] = payload
        header = self._header(DIRECTION_REQUEST, session, slot)
        nonce = os.urandom(NONCE_BYTES)
        frame = header + nonce + self._aead.encrypt(nonce, bytes(plain), header)
        if len(frame) != self.profile.frame_bytes:
            raise AssertionError("fixed request frame width changed")
        return frame

    def encode_noop(self, session: int, slot: int) -> bytes:
        # The identifier is fresh trusted plaintext and is never interpreted as work.
        return self.encode_request(session, slot, action=ACTION_NOOP, provider=0,
                                   operation_id=os.urandom(16).hex())

    def decode_response(self, frame: bytes) -> DecodedResult | None:
        header = parse_public_header(frame)
        if header.direction != DIRECTION_RESPONSE or header.profile_id != self.profile.profile_id:
            raise ValueError("response profile/direction mismatch")
        expected_session = self._response_next // self.profile.slots
        expected_slot = self._response_next % self.profile.slots + 1
        if (header.session, header.slot) != (expected_session, expected_slot):
            raise ValueError("duplicate, replayed, or non-monotonic response")
        nonce_at = PUBLIC_HEADER.size
        nonce = frame[nonce_at:nonce_at + NONCE_BYTES]
        plain = self._aead.decrypt(nonce, frame[nonce_at + NONCE_BYTES:], frame[:PUBLIC_HEADER.size])
        self._response_next += 1
        if plain[0] == STATUS_WAIT:
            return None
        payload_length = struct.unpack_from("!H", plain, 36)[0]
        if payload_length > min(RESULT_PAYLOAD_BYTES, len(plain) - 48):
            raise ValueError("invalid result payload length")
        operation_id = plain[4:36].rstrip(b"\0").decode("utf-8")
        return DecodedResult(plain[0], operation_id, bytes(plain[48:48 + payload_length]),
                             header.session, header.slot)

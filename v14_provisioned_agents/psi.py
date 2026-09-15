from __future__ import annotations

import hashlib
import struct
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable

from .models import DUMMY_AGENT_ID, PIR_ROW_HANDLE_BYTES, PIRRowHandle, validate_agent_id


APSI_REPOSITORY = "https://github.com/microsoft/APSI"
APSI_COMMIT = "548745efdb37b1d7d948c761a772488747ca16ab"
APSI_VERSION = "0.13.1"
APSI_ITEM_BYTES = 16
PSI_RECEIVER_CARDINALITY = 1
_REAL_DOMAIN = b"OAE-PROVISIONED-AGENT-ID-v1\x00"
_IDLE_DOMAIN = b"OAE-IDLE-AGENT-ID-v1\x00"
_REQUEST = struct.Struct(">4sHHQ16s")
_RESPONSE = struct.Struct(">4sHHQHHB3x32s8Q")
_INPUT_HEADER = struct.Struct(">8sIII")


class APSIError(RuntimeError):
    pass


def _u64(value: int) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**64:
        raise ValueError("identifier outside unsigned 64-bit domain")
    return value.to_bytes(8, "big")


def encode_real_item(agent_id: int) -> bytes:
    return hashlib.sha256(_REAL_DOMAIN + _u64(validate_agent_id(agent_id))).digest()[:16]


def encode_idle_item(dummy_id: int = DUMMY_AGENT_ID) -> bytes:
    if dummy_id < (1 << 63):
        raise ValueError("idle identifier is outside reserved namespace")
    return hashlib.sha256(_IDLE_DOMAIN + _u64(dummy_id)).digest()[:16]


def write_sender_input(
    mapping: Iterable[tuple[int, PIRRowHandle]], path: Path
) -> dict[str, object]:
    pairs = [(encode_real_item(agent_id), handle.encode()) for agent_id, handle in mapping]
    if not pairs or len(pairs) > 100_000:
        raise ValueError("APSI sender requires 1..100000 provisioned Agents")
    if len(set(item for item, _ in pairs)) != len(pairs):
        raise ValueError("duplicate/colliding APSI item")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(_INPUT_HEADER.pack(b"OAEDB014", len(pairs), 16, PIR_ROW_HANDLE_BYTES))
        for item, label in pairs:
            stream.write(item)
            stream.write(label)
    return {
        "items": len(pairs),
        "item_bytes": 16,
        "label_bytes": 32,
        "file_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


@dataclass(frozen=True)
class APSIWireMetrics:
    oprf_request_bytes: int
    oprf_response_bytes: int
    query_request_bytes: int
    query_response_bytes: int
    oprf_ns: int
    query_construction_ns: int
    query_roundtrip_ns: int
    result_processing_ns: int

    @property
    def request_bytes(self) -> int:
        return self.oprf_request_bytes + self.query_request_bytes

    @property
    def response_bytes(self) -> int:
        return self.oprf_response_bytes + self.query_response_bytes


@dataclass(frozen=True)
class APSIResult:
    row_handle: PIRRowHandle | None
    wire: APSIWireMetrics


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    value = bytearray()
    while len(value) < size:
        chunk = stream.read(size - len(value))
        if not chunk:
            raise APSIError("APSI receiver bridge closed its response stream")
        value.extend(chunk)
    return bytes(value)


class RealLabeledAPSIClient:
    production_ready = True

    def __init__(
        self,
        receiver_binary: Path,
        endpoint: str,
        *,
        expected_sha256: str | None = None,
        threads: int = 1,
        stderr: BinaryIO | int | None = subprocess.PIPE,
    ):
        receiver_binary = receiver_binary.resolve()
        digest = hashlib.sha256(receiver_binary.read_bytes()).hexdigest()
        if expected_sha256 and digest != expected_sha256.lower():
            raise APSIError("APSI receiver binary hash mismatch")
        self.binary_sha256 = digest
        self._request_id = 0
        self._lock = threading.Lock()
        self.process = subprocess.Popen(
            [str(receiver_binary), "--endpoint", endpoint, "--threads", str(threads)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
        )

    def close(self) -> None:
        if self.process.poll() is None:
            assert self.process.stdin is not None
            self.process.stdin.close()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=10)

    def __enter__(self) -> "RealLabeledAPSIClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def query(self, agent_id: int | None) -> APSIResult:
        item = encode_idle_item() if agent_id is None else encode_real_item(agent_id)
        with self._lock:
            if self.process.poll() is not None:
                raise APSIError("APSI receiver bridge is not running")
            assert self.process.stdin is not None and self.process.stdout is not None
            self._request_id += 1
            self.process.stdin.write(_REQUEST.pack(b"OAQ4", 1, 1, self._request_id, item))
            self.process.stdin.flush()
            values = _RESPONSE.unpack(_read_exact(self.process.stdout, _RESPONSE.size))
            magic, version, count, request_id, status, reserved, found, label, *metrics = values
            if (magic, version, count, request_id, status, reserved) != (
                b"OAR4", 1, 1, self._request_id, 0, 0
            ):
                raise APSIError("invalid APSI bridge response")
            if found not in (0, 1) or (not found and any(label)):
                raise APSIError("invalid APSI match representation")
            return APSIResult(
                PIRRowHandle.decode(label) if found else None,
                APSIWireMetrics(*metrics),
            )


def require_real_apsi(value: object) -> None:
    if not isinstance(value, RealLabeledAPSIClient) or not value.production_ready:
        raise APSIError("REAL_PSI_REQUIRED: mock/plaintext membership is forbidden")

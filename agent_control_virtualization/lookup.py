from __future__ import annotations

import time
import struct
from dataclasses import dataclass
from typing import Protocol

from .ir import CAPSULE_BYTES


class PrivateAgentLookup(Protocol):
    def lookup(self, index: int) -> bytes: ...
    def public_metrics(self) -> dict[str, object]: ...


@dataclass
class MockLookupResult:
    row: bytes
    latency_us: float
    server_cpu_us: float
    request_bytes: int
    response_bytes: int
    host_visible_index: int


class MockPrivateLookup:
    """NON-CRYPTOGRAPHIC architectural backend.

    This direct array lookup leaks the requested index and therefore provides
    no target privacy. It exists only to measure row size and runtime plumbing.
    """

    security_status = "MOCK_PRIVATE_LOOKUP_NON_CRYPTOGRAPHIC"

    def __init__(self, row_count: int, prototype_rows: tuple[bytes, ...]):
        if not prototype_rows or any(len(row) != CAPSULE_BYTES for row in prototype_rows):
            raise ValueError("fixed capsule rows required")
        started = time.perf_counter_ns()
        self.row_count = row_count
        self.storage = bytearray(row_count * CAPSULE_BYTES)
        for index in range(row_count):
            # Controlled generated variants preserve a real compiled capsule's
            # ABI while assigning every logical registry entry a distinct ID.
            row = bytearray(prototype_rows[index % len(prototype_rows)])
            struct.pack_into("!I", row, 8, index)
            start = index * CAPSULE_BYTES
            self.storage[start:start + CAPSULE_BYTES] = row
        self.preprocessing_us = (time.perf_counter_ns() - started) / 1000

    def lookup_measured(self, index: int) -> MockLookupResult:
        if not 0 <= index < self.row_count: raise IndexError(index)
        started = time.perf_counter_ns(); begin = index * CAPSULE_BYTES
        row = bytes(self.storage[begin:begin + CAPSULE_BYTES])
        elapsed = (time.perf_counter_ns() - started) / 1000
        return MockLookupResult(row, elapsed, elapsed, 8, CAPSULE_BYTES, index)

    def lookup(self, index: int) -> bytes:
        return self.lookup_measured(index).row

    def public_metrics(self) -> dict[str, object]:
        return {"backend": self.security_status, "cryptographic_privacy": False,
                "server_storage_bytes": len(self.storage), "client_memory_bytes": CAPSULE_BYTES,
                "preprocessing_us": self.preprocessing_us}

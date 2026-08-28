from __future__ import annotations

import json
import os
import queue
import socket
import struct
import threading
import time
from dataclasses import dataclass, fields
from multiprocessing.queues import Queue
from pathlib import Path

from privacy_kernel.protocol import (CanonicalProfile, DIRECTION_REQUEST,
                                     DIRECTION_RESPONSE, parse_public_header)


FORBIDDEN_PROXY_FIELDS = frozenset({
    "logical_agent_id", "registry_index", "capsule", "opcode", "action",
    "tool", "provider", "prompt", "arguments", "operation_id", "payload",
    "result", "key", "private_workload",
})


@dataclass(frozen=True)
class ProxyConfig:
    address: str
    public_profile: CanonicalProfile
    host_log_path: Path


def assert_public_proxy_schema() -> None:
    names = {item.name.lower() for item in fields(ProxyConfig)}
    if names & FORBIDDEN_PROXY_FIELDS:
        raise AssertionError("private field entered Cloud Slot Proxy schema")


def _clock_ns() -> int:
    return time.time_ns() if os.name == "nt" else time.monotonic_ns()


def _wait_until(deadline: int) -> None:
    while True:
        remaining = deadline - _clock_ns()
        if remaining <= 0:
            return
        if remaining > 2_000_000:
            time.sleep((remaining - 1_000_000) / 1e9)
        else:
            time.sleep(0)


def _read_exact(connection: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        block = connection.recv(size - len(chunks))
        if not block:
            raise ConnectionError("unexpected tunnel close")
        chunks.extend(block)
    return bytes(chunks)


def _socket_address(value: str) -> tuple[str, int]:
    host, separator, port = value.rpartition(":")
    if not separator or not host or not port.isdigit():
        raise ValueError("invalid public Gateway address")
    return host, int(port)


def run_cloud_slot_proxy(config: ProxyConfig, opaque_requests: Queue,
                         opaque_responses: Queue, readiness: Queue) -> None:
    """Forward opaque frames. No key or private descriptor crosses this API."""
    assert_public_proxy_schema()
    profile = config.public_profile
    connection = socket.create_connection(_socket_address(config.address), timeout=10)
    connection.settimeout(None)
    handshake = _read_exact(connection, 16)
    if handshake[:8] != b"CAGV2T0!":
        raise ValueError("invalid public Gateway handshake")
    t0 = struct.unpack("!Q", handshake[8:])[0]
    readiness.put({"ready": True, "public_t0_ns": t0, "pid": os.getpid()})
    total = profile.sessions * profile.slots
    events: list[dict[str, int | str]] = []
    errors: queue.Queue[BaseException] = queue.Queue()

    def receive() -> None:
        try:
            for ordinal in range(total):
                frame = _read_exact(connection, profile.frame_bytes)
                received = _clock_ns()
                header = parse_public_header(frame)
                expected = (ordinal // profile.slots, ordinal % profile.slots + 1)
                if header.direction != DIRECTION_RESPONSE or (header.session, header.slot) != expected:
                    raise ValueError("invalid public response sequence")
                opaque_responses.put(frame)
                events.append({"direction": "RESPONSE", "session": header.session,
                               "slot": header.slot, "frame_bytes": len(frame),
                               "actual_socket_receive_ns": received,
                               "destination": "CommonActionGatewayV2"})
        except BaseException as exc:  # propagated after the fixed loop
            errors.put(exc)

    receiver = threading.Thread(target=receive, daemon=True)
    receiver.start()
    for ordinal in range(total):
        frame = opaque_requests.get(timeout=30)
        if not isinstance(frame, bytes) or len(frame) != profile.frame_bytes:
            raise ValueError("proxy accepts only fixed opaque bytes")
        header = parse_public_header(frame)
        expected = (ordinal // profile.slots, ordinal % profile.slots + 1)
        if header.direction != DIRECTION_REQUEST or header.profile_id != profile.profile_id:
            raise ValueError("invalid opaque request public header")
        if (header.session, header.slot) != expected:
            raise ValueError("duplicate, replayed, or non-monotonic opaque request")
        deadline = t0 + header.session * profile.session_span_ns + header.slot * profile.request_delta_ns
        _wait_until(deadline)
        sent = _clock_ns()
        connection.sendall(frame)
        events.append({"direction": "REQUEST", "session": header.session,
                       "slot": header.slot, "frame_bytes": len(frame),
                       "scheduled_send_ns": deadline, "actual_socket_send_ns": sent,
                       "destination": "CommonActionGatewayV2"})
    receiver.join(timeout=30)
    connection.close()
    if receiver.is_alive():
        raise TimeoutError("proxy response receiver did not finish")
    if not errors.empty():
        raise errors.get()
    config.host_log_path.parent.mkdir(parents=True, exist_ok=True)
    with config.host_log_path.open("w", encoding="utf-8") as handle:
        for event in sorted(events, key=lambda item: (int(item["session"]), int(item["slot"]), str(item["direction"]))):
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")

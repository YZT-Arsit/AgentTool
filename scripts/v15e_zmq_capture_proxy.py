from __future__ import annotations

import argparse
import hashlib
import json
import signal
import time
from pathlib import Path
from typing import Any

import numpy as np
import zmq


def summarize(parts: list[bytes]) -> dict[str, Any]:
    raw = b"".join(parts)
    values = np.frombuffer(raw, dtype=np.uint8)
    offsets = np.linspace(0, max(0, len(raw) - 1), 64, dtype=np.int64)
    return {
        "serialized_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_histogram_32": np.bincount(values // 8, minlength=32).tolist(),
        "fixed_offset_bytes_64": values[offsets].tolist() if len(raw) else [0] * 64,
    }


class Observation:
    def __init__(self, ordinal: int) -> None:
        self.ordinal = ordinal
        self.requests: list[tuple[int, list[bytes]]] = []
        self.responses: list[tuple[int, list[bytes]]] = []

    def complete(self) -> bool:
        return len(self.requests) == 2 and len(self.responses) >= 2

    def record(self) -> dict[str, Any]:
        if not self.complete():
            raise RuntimeError(
                f"incomplete APSI observation {self.ordinal}: "
                f"requests={len(self.requests)} responses={len(self.responses)}"
            )
        oprf_req_ns, oprf_req = self.requests[0]
        query_req_ns, query_req = self.requests[1]
        oprf_resp_ns, oprf_resp = self.responses[0]
        result_parts = [part for _, frames in self.responses[1:] for part in frames]
        result_first_ns = self.responses[1][0]
        result_last_ns = self.responses[-1][0]
        return {
            "schema": "AgentTool.V15EAPSIApplicationCapture/1",
            "observation_ordinal": self.ordinal,
            "timestamp_type": "APPLICATION_PROTOCOL_TIMESTAMP_MONOTONIC_NS",
            "oprf_request": {
                "direction": "RECEIVER_TO_SERVER",
                "server_receive_monotonic_ns": oprf_req_ns,
                "message_count": 1,
                "message_serialized_lengths": [sum(map(len, oprf_req))],
                **summarize(oprf_req),
            },
            "oprf_response": {
                "direction": "SERVER_TO_RECEIVER",
                "server_send_monotonic_ns": oprf_resp_ns,
                "message_count": 1,
                "message_serialized_lengths": [sum(map(len, oprf_resp))],
                **summarize(oprf_resp),
            },
            "query": {
                "direction": "RECEIVER_TO_SERVER",
                "server_receive_monotonic_ns": query_req_ns,
                "message_count": 1,
                "message_serialized_lengths": [sum(map(len, query_req))],
                **summarize(query_req),
            },
            "result": {
                "direction": "SERVER_TO_RECEIVER",
                "server_first_send_monotonic_ns": result_first_ns,
                "server_last_send_monotonic_ns": result_last_ns,
                "message_count": len(self.responses) - 1,
                "message_serialized_lengths": [
                    sum(map(len, frames)) for _, frames in self.responses[1:]
                ],
                **summarize(result_parts),
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(args.output)

    context = zmq.Context()
    frontend = context.socket(zmq.ROUTER)
    backend = context.socket(zmq.DEALER)
    frontend.bind(args.listen)
    backend.connect(args.upstream)
    poller = zmq.Poller()
    poller.register(frontend, zmq.POLLIN)
    poller.register(backend, zmq.POLLIN)
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    receiver_id: bytes | None = None
    current: Observation | None = None
    ordinal = 0
    with args.output.open("x", encoding="utf-8", buffering=1) as stream:
        try:
            while running:
                events = dict(poller.poll(100))
                # Drain server output first so a following OPRF request cannot
                # close the preceding observation before its final result part.
                if backend in events:
                    frames = backend.recv_multipart()
                    if receiver_id is None:
                        raise RuntimeError("APSI response arrived without a request")
                    if current is not None:
                        current.responses.append((time.monotonic_ns(), frames))
                    frontend.send_multipart([receiver_id, *frames])
                if frontend in events:
                    frames = frontend.recv_multipart()
                    if len(frames) < 3:
                        raise RuntimeError(f"unexpected APSI request frame count {len(frames)}")
                    new_receiver_id, app_frames = frames[0], frames[1:]
                    if receiver_id is not None and new_receiver_id != receiver_id:
                        raise RuntimeError("V15E capture proxy permits one persistent receiver")
                    receiver_id = new_receiver_id
                    serialized_bytes = sum(len(part) for part in app_frames)
                    # APSI performs one public parameter exchange when the
                    # persistent receiver starts. It is not an Agent-access
                    # observation. The frozen v0.13.1 operation sizes let the
                    # proxy identify that setup request without parsing or
                    # exposing any private protocol state.
                    if serialized_bytes == 64:
                        backend.send_multipart(app_frames)
                        continue
                    if serialized_bytes == 104:
                        if current is not None:
                            stream.write(json.dumps(current.record(), separators=(",", ":")) + "\n")
                            ordinal += 1
                        current = Observation(ordinal)
                    elif serialized_bytes != 697_972:
                        raise RuntimeError(f"unexpected APSI serialized request bytes {serialized_bytes}")
                    if current is None:
                        raise RuntimeError("APSI query arrived before OPRF request")
                    current.requests.append((time.monotonic_ns(), app_frames))
                    backend.send_multipart(app_frames)
        finally:
            if current is not None:
                stream.write(json.dumps(current.record(), separators=(",", ":")) + "\n")
            frontend.close(0)
            backend.close(0)
            context.term()


if __name__ == "__main__":
    main()

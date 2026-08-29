from __future__ import annotations

import argparse
import base64
import json
import random
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class State:
    def __init__(self, name: str, minimum_ms: int, maximum_ms: int, effectful: bool, seed: int):
        self.name = name
        self.minimum_ms = minimum_ms
        self.maximum_ms = maximum_ms
        self.effectful = effectful
        self.random = random.Random(seed)
        self.lock = threading.Lock()
        self.calls: dict[str, int] = {}
        self.effects: set[str] = set()

    def execute(self, operation_id: str, payload: bytes) -> bytes:
        with self.lock:
            self.calls[operation_id] = self.calls.get(operation_id, 0) + 1
            delay = self.random.randint(self.minimum_ms, self.maximum_ms)
            if self.effectful:
                self.effects.add(operation_id)
        time.sleep(delay / 1000.0)
        return f"{self.name}:{operation_id}:{payload.decode(errors='replace')}".encode()

    def metrics(self) -> dict[str, object]:
        with self.lock:
            return {
                "provider": self.name,
                "total_calls": sum(self.calls.values()),
                "unique_operations": len(self.calls),
                "duplicate_calls": sum(max(0, value - 1) for value in self.calls.values()),
                "effect_count": len(self.effects),
                "calls_by_operation": dict(sorted(self.calls.items())),
            }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--min-delay-ms", type=int, required=True)
    parser.add_argument("--max-delay-ms", type=int, required=True)
    parser.add_argument("--effectful", action="store_true")
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    state = State(args.name, args.min_delay_ms, args.max_delay_ms, args.effectful, args.seed)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/execute":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(length))
                operation_id = str(request["operation_id"])
                payload = base64.b64decode(request.get("payload", ""))
                result = state.execute(operation_id, payload)
                encoded = json.dumps({"status": "OK", "payload": base64.b64encode(result).decode()}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
            except Exception:
                self.send_error(400)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    stopping = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stopping.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(json.dumps({"ready": True, "endpoint": f"http://127.0.0.1:{server.server_port}/execute"}), flush=True)
    try:
        server.serve_forever(poll_interval=0.05)
    finally:
        args.metrics.parent.mkdir(parents=True, exist_ok=True)
        args.metrics.write_text(json.dumps(state.metrics(), indent=2) + "\n", encoding="utf-8")
        server.server_close()


if __name__ == "__main__":
    main()


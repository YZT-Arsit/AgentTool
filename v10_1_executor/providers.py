from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from canonical_v9.runner import Providers

from .models import ActionOutcome, CaseSpec


PROVIDER_NAMES = {route: values[0] for route, values in Providers.definitions.items()}


def _provider_name(capability: str) -> str:
    return {
        "tool.a": "TOOL_A",
        "tool.b": "TOOL_B",
        "tool.read": "TOOL_READ",
        "tool.idem": "TOOL_IDEM",
        "tool.nonidem": "TOOL_NONIDEM",
        "external.local": "EXTERNAL_LOCAL",
    }[capability]


def _provider_result(name: str, operation_id: str, argument: str) -> str:
    return f"{name}:{operation_id}:{argument}"


def run_native_provider(case: CaseSpec, argument: str) -> ActionOutcome:
    """Execute the independent local reference provider contract."""

    request = {"operation_id": case.operation_id, "payload": argument}
    started = time.monotonic_ns()
    if case.scenario == "SUCCESS":
        result = _provider_result(_provider_name(case.capability), case.operation_id, argument)
        effect_count = int(case.effect_semantics != "READ_ONLY")
        outcome = f"{case.effect_semantics}:SUCCESS"
    elif case.scenario == "ERROR":
        result = ""
        effect_count = 0
        outcome = f"{case.effect_semantics}:ERROR"
    else:
        # This is an actual bounded wait in the local reference path, not a
        # manifest-derived result.  It intentionally stays outside holdout use.
        deadline = 0.010
        completed = threading.Event()

        def slow() -> None:
            time.sleep(0.050)
            completed.set()

        threading.Thread(target=slow, daemon=True).start()
        if completed.wait(deadline):
            raise AssertionError("bounded-timeout fixture unexpectedly completed")
        result = ""
        effect_count = 0
        outcome = f"{case.effect_semantics}:BOUNDED_TIMEOUT"
    return ActionOutcome(
        result=result,
        effect_count=effect_count,
        outcome_semantics=outcome,
        provider_request=request,
        runtime_evidence={"provider_started_ns": started, "provider_finished_ns": time.monotonic_ns(), "scenario_observed": case.scenario},
    )


@dataclass
class _ObservedCall:
    route: str
    operation_id: str
    payload: str
    status: str


class EvidenceProviders:
    """Local HTTP providers that expose actual request evidence to the harness.

    This object satisfies canonical_v9.runner.route_specs without changing the
    accepted canonical runner.  Every canonical action still crosses real HTTP.
    """

    def __init__(self, scenario_by_operation: dict[str, str] | None = None):
        self.scenario_by_operation = scenario_by_operation or {}
        self.endpoints: dict[str, str] = {}
        self.calls: list[_ObservedCall] = []
        self.effects: set[str] = set()
        self._servers: list[ThreadingHTTPServer] = []
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()

    def __enter__(self) -> "EvidenceProviders":
        for route, (name, _minimum, _maximum, effectful) in Providers.definitions.items():
            server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler(route, name, effectful))
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
            thread.start()
            self._servers.append(server)
            self._threads.append(thread)
            self.endpoints[route] = f"http://127.0.0.1:{server.server_port}/execute"
        return self

    def _handler(self, route: str, name: str, effectful: bool) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(length))
                operation_id = str(request["operation_id"])
                payload = base64.b64decode(request.get("payload", "")).decode("utf-8", errors="replace")
                scenario = owner.scenario_by_operation.get(operation_id, "SUCCESS")
                if scenario == "BOUNDED_TIMEOUT":
                    time.sleep(0.080)
                status = "OK" if scenario == "SUCCESS" else scenario
                with owner._lock:
                    owner.calls.append(_ObservedCall(route, operation_id, payload, status))
                    if effectful and scenario == "SUCCESS":
                        owner.effects.add(operation_id)
                if scenario == "ERROR":
                    self.send_error(503)
                    return
                result = _provider_result(name, operation_id, payload).encode()
                encoded = json.dumps({"status": "OK", "payload": base64.b64encode(result).decode()}).encode()
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

            def log_message(self, _format: str, *_args: object) -> None:
                return

        return Handler

    def __exit__(self, *_args: object) -> None:
        for server in self._servers:
            server.shutdown()
        for server in self._servers:
            server.server_close()
        for thread in self._threads:
            thread.join(timeout=2)

    def observed(self, operation_id: str) -> dict[str, Any]:
        values = [value for value in self.calls if value.operation_id == operation_id]
        if len(values) != 1:
            raise AssertionError(f"expected one provider observation for {operation_id}, got {len(values)}")
        value = values[0]
        return {"operation_id": value.operation_id, "payload": value.payload}

    def outcome(self, operation_id: str) -> str:
        values = [value.status for value in self.calls if value.operation_id == operation_id]
        if len(values) != 1:
            raise AssertionError("provider outcome evidence is missing or duplicated")
        return values[0]

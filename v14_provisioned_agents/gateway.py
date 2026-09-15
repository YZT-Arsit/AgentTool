from __future__ import annotations

import base64
import json
import subprocess
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from v12_timing.profile import duplex_response_anchor_p10_profile


V4R8_RUNNER_SHA256 = "84fc61e363ed587ba5c200be12ebb66c9a71c69daad39950f1b50e66cd363437"
ROUTE = "internet-agent-repository"
POLICY = "internet-agent-artifact-read-v1"
# The frozen 768-byte response bucket includes BHTTP/OAE semantic overhead.
# 320 bytes leaves a measured safety margin; one 1,024-byte record uses four
# private chunks without changing the 521-cell public transcript.
CHUNK_BYTES = 320


@dataclass(frozen=True)
class GatewayArtifactSession:
    artifact: bytes | None
    public_profile: dict[str, object]
    result: dict[str, object]


def _provider(artifact: bytes):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                request = json.loads(base64.b64decode(body["payload"]))
                chunk = int(request["chunk"])
                payload = artifact[chunk * CHUNK_BYTES : (chunk + 1) * CHUNK_BYTES]
                response = json.dumps(
                    {"status": "OK", "payload": base64.b64encode(payload).decode("ascii")},
                    separators=(",", ":"),
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers(); self.wfile.write(response)
            except Exception:
                self.send_error(400)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def run_frozen_v4r8_gateway_artifact_session(
    runner: Path,
    output: Path,
    *,
    agent_id: int | None,
    artifact: bytes | None,
) -> GatewayArtifactSession:
    """Carry an Internet-repository artifact through the frozen common Gateway.

    Provisioned/idle cases run the same 521-cell public profile with no real
    repository action. Unprovisioned cases split one 1,024-byte artifact over
    two fixed-profile external actions; no Agent-specific destination exists.
    """
    import hashlib

    runner = runner.resolve()
    if hashlib.sha256(runner.read_bytes()).hexdigest() != V4R8_RUNNER_SHA256:
        raise RuntimeError("frozen V4R8 Gateway runner hash mismatch")
    if (agent_id is None) != (artifact is None):
        raise ValueError("AgentID and repository artifact must be jointly present/absent")
    output.mkdir(parents=True, exist_ok=False)
    profile = duplex_response_anchor_p10_profile()
    plan = profile.go_plan_fields()
    plan["state_directory"] = str(output / "gateway_state")
    plan["actions"] = []
    plan["routes"] = []
    plan["scheduler_tolerance_ms"] = 3
    plan["preparation_lead_ms"] = 1
    actions: list[dict[str, object]] = []
    server = thread = None
    if artifact is not None:
        server, thread = _provider(artifact)
        endpoint = f"http://127.0.0.1:{server.server_port}/execute"
        plan["routes"] = [{
            "route_handle": ROUTE,
            "action_kind": "REAL_EXTERNAL_HTTP",
            "effect_semantics": "READ_ONLY",
            "endpoint": endpoint,
            "policy_id": POLICY,
        }]
        for index in range((len(artifact) + CHUNK_BYTES - 1) // CHUNK_BYTES):
            operation_id = f"v14-repository-{agent_id}-chunk-{index}"
            request = json.dumps(
                {"agent_id": agent_id, "chunk": index}, separators=(",", ":")
            ).encode()
            actions.append({
                "operation_id": operation_id,
                "action_kind": "REAL_EXTERNAL_HTTP",
                "route_handle": ROUTE,
                "effect_semantics": "READ_ONLY",
                "policy_id": POLICY,
                "protected_arguments": base64.b64encode(request).decode("ascii"),
            })
    plan_path = output / "private_plan.json"
    result_path = output / "result.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [str(runner), "--online", "--plan", str(plan_path), "--output", str(result_path)],
            cwd=runner.parents[2], text=True, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
        )
        assert process.stdin is not None and process.stdout is not None
        first = process.stdout.readline()
        event = json.loads(first)
        if event.get("type") != "SESSION_READY":
            raise RuntimeError(f"frozen V4R8 Gateway did not become ready: {event}")
        for action in actions:
            process.stdin.write(json.dumps({"type": "SUBMIT_RESOLVED_ACTION", "action": action}) + "\n")
        process.stdin.flush(); process.stdin.close()
        remaining = process.stdout.read()
        stderr = process.stderr.read() if process.stderr is not None else ""
        returncode = process.wait()
    finally:
        if server is not None:
            server.shutdown(); server.server_close()
            assert thread is not None; thread.join(timeout=5)
    (output / "stdout.txt").write_text(first + remaining, encoding="utf-8")
    (output / "stderr.txt").write_text(stderr, encoding="utf-8")
    if returncode:
        raise RuntimeError(f"frozen V4R8 Gateway session failed: {stderr}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not (
        result["session_status"] == "COMPLETE"
        and result["public_transcript_complete"] is True
        and result["emitted_cells"] == 521
        and result["request_final_bytes"] == 1079
        and result["response_final_bytes"] == 800
    ):
        raise RuntimeError("frozen V4R8 Gateway public transcript is incomplete")
    recovered = None
    if artifact is not None:
        ordered = sorted(result["results"], key=lambda item: item["operation_id"])
        recovered = b"".join(base64.b64decode(item["payload"]) for item in ordered)
        if recovered != artifact:
            raise RuntimeError("Gateway artifact chunk reconstruction failed")
    public = {
        "profile_id": result["profile_id"],
        "relay_cells": result["emitted_cells"],
        "request_bytes": result["request_final_bytes"],
        "response_bytes": result["response_final_bytes"],
        "public_transcript_complete": result["public_transcript_complete"],
        "common_gateway_endpoint": True,
        "agent_specific_gateway_destination": False,
    }
    return GatewayArtifactSession(recovered, public, result)

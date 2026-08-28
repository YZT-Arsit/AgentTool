from __future__ import annotations

import csv
import json
import os
import queue
import secrets
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class V2Profile:
    name: str
    frame_bytes: int
    slots: int
    sessions: int
    request_delta_ns: int
    response_delta_ns: int
    mask_ns: int
    start_delay_ns: int
    inter_session_gap_ns: int


@dataclass(frozen=True)
class EmulatorDefinition:
    name: str
    min_delay_ms: int
    max_delay_ms: int
    cpu_work_ms: int = 0
    background_workers: int = 0


def _go(root: Path) -> Path:
    bundled = root / ".toolchains" / "go" / "Go" / "bin" / "go.exe"
    if bundled.exists():
        return bundled
    system = shutil.which("go")
    if not system:
        raise FileNotFoundError("Go toolchain not found")
    return Path(system)


def build_binaries(root: Path) -> dict[str, Path]:
    module = root / "common_action_gateway_v2"
    output = module / "bin"
    output.mkdir(exist_ok=True)
    suffix = ".exe" if os.name == "nt" else ""
    commands = {
        "worker": "gateway-worker",
        "pacer": "gateway-pacer",
        "client": "gateway-cloud-client",
        "provider": "local-provider-emulator",
    }
    binaries: dict[str, Path] = {}
    for role, command in commands.items():
        target = output / f"{command}{suffix}"
        subprocess.run(
            [str(_go(root)), "build", "-o", str(target), f"./cmd/{command}"],
            cwd=module,
            check=True,
        )
        binaries[role] = target
    return binaries


def _read_ready(process: subprocess.Popen[str], timeout: float = 10.0) -> str:
    messages: queue.Queue[str] = queue.Queue()

    def read() -> None:
        messages.put(process.stdout.readline().strip() if process.stdout else "")

    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    try:
        line = messages.get(timeout=timeout)
    except queue.Empty as exc:
        process.terminate()
        raise RuntimeError("process readiness timeout") from exc
    if not line.startswith("READY"):
        stderr = process.stderr.read() if process.stderr else ""
        raise RuntimeError(f"process failed readiness: {line!r} {stderr}")
    return line


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _affinity_plan() -> tuple[int, int, int]:
    cpus = os.cpu_count() or 1
    if cpus >= 3:
        return 0, 1, 2
    if cpus == 2:
        return 0, 1, 1
    return -1, -1, -1


def run_gateway_v2(
    root: Path,
    output: Path,
    profile: V2Profile,
    sessions: list[dict[str, object]],
    emulator_definitions: Iterable[EmulatorDefinition],
) -> dict[str, object]:
    """Run one new local V2 workload without touching any V1 artifact."""

    root = root.resolve()
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite completed output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    if len(sessions) != profile.sessions:
        raise ValueError("profile/session mismatch")
    binaries = build_binaries(root)
    pacer_cpu, worker_cpu, client_cpu = _affinity_plan()
    key = secrets.token_hex(16)
    profile_path = output / "public_profile.json"
    workload_path = output / "private_workload.json"
    providers_path = output / "private_provider_config.json"
    _write_json(profile_path, asdict(profile))
    _write_json(workload_path, {"sessions": sessions})
    with (output / "private_ground_truth.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("session", "label", "real_actions"))
        writer.writeheader()
        for index, session in enumerate(sessions):
            writer.writerow({"session": index, "label": session["label"], "real_actions": len(session["actions"])})

    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    providers: list[subprocess.Popen[str]] = []
    endpoints: dict[str, str] = {}
    try:
        for index, definition in enumerate(emulator_definitions):
            process = subprocess.Popen(
                [
                    str(binaries["provider"]), "--listen", "127.0.0.1:0", "--name", definition.name,
                    "--min-delay-ms", str(definition.min_delay_ms), "--max-delay-ms", str(definition.max_delay_ms),
                    "--cpu-work-ms", str(definition.cpu_work_ms), "--background-workers", str(definition.background_workers),
                    "--seed", str(7000 + index), "--cpu", str(worker_cpu), "--effectful",
                ],
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=hidden,
            )
            providers.append(process)
            ready = _read_ready(process)
            endpoints[definition.name] = ready.split()[1]
        _write_json(providers_path, {"endpoints": endpoints,
                                     "effectful": {name: True for name in endpoints},
                                     "timeout_ms": 4000, "allow_generic_http": False})

        request_ring = output / "request_ring.shared"
        result_ring = output / "result_ring.shared"
        expected = profile.sessions * profile.slots
        worker = subprocess.Popen(
            [
                str(binaries["worker"]), "--request-ring", str(request_ring), "--result-ring", str(result_ring),
                "--capacity", str(max(4096, expected * 2)), "--frame-bytes", str(profile.frame_bytes),
                "--expected-frames", str(expected), "--key", key, "--providers", str(providers_path),
                "--profile", str(profile_path),
                "--private-log", str(output / "worker_private.jsonl"), "--cpu", str(worker_cpu),
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=hidden,
        )
        worker_ready = _read_ready(worker)

        pacer = subprocess.Popen(
            [
                str(binaries["pacer"]), "--listen", "127.0.0.1:0", "--profile", str(profile_path),
                "--request-ring", str(request_ring), "--result-ring", str(result_ring), "--key", key,
                "--host-log", str(output / "pacer_socket_boundary.jsonl"),
                "--private-log", str(output / "pacer_private_delivery.jsonl"),
                "--status", str(output / "pacer_status.json"), "--cpu", str(pacer_cpu),
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=hidden,
        )
        pacer_ready = _read_ready(pacer)
        address = pacer_ready.split()[1]
        client = subprocess.Popen(
            [
                str(binaries["client"]), "--address", address, "--profile", str(profile_path),
                "--workload", str(workload_path), "--key", key,
                "--host-log", str(output / "cloud_socket_boundary.jsonl"), "--cpu", str(client_cpu),
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=hidden,
        )
        timeout = max(30.0, profile.sessions * profile.slots * max(profile.request_delta_ns, profile.response_delta_ns) / 1e9 * 2 + 15)
        client_stdout, client_stderr = client.communicate(timeout=timeout)
        if client.returncode:
            raise RuntimeError(f"cloud client failed: {client_stderr}")
        pacer_stdout, pacer_stderr = pacer.communicate(timeout=15)
        if pacer.returncode:
            raise RuntimeError(f"pacer failed: {pacer_stderr}")
        worker_stdout, worker_stderr = worker.communicate(timeout=10)
        if worker.returncode:
            raise RuntimeError(f"worker failed: {worker_stderr}")
        (output / "process_output.json").write_text(json.dumps({
            "worker_ready": worker_ready,
            "pacer_ready": pacer_ready,
            "worker_stdout": worker_stdout,
            "worker_stderr": worker_stderr,
            "pacer_stdout": pacer_stdout,
            "pacer_stderr": pacer_stderr,
            "client_stdout": client_stdout,
            "client_stderr": client_stderr,
            "provider_pids": [process.pid for process in providers],
            "worker_pid": worker.pid,
            "pacer_pid": pacer.pid,
            "client_pid": client.pid,
        }, indent=2), encoding="utf-8")

        merged: dict[tuple[int, int], dict[str, object]] = {}
        for event in _jsonl(output / "cloud_socket_boundary.jsonl") + _jsonl(output / "pacer_socket_boundary.jsonl"):
            key_tuple = (int(event["session"]), int(event["slot"]))
            row = merged.setdefault(key_tuple, {"session": key_tuple[0], "slot": key_tuple[1]})
            direction = event["direction"]
            if direction == "REQUEST" and event.get("scheduled_send_ns"):
                row["cloud_request_scheduled_ns"] = event["scheduled_send_ns"]
                row["cloud_request_send_ns"] = event["actual_socket_send_ns"]
                row["request_bytes"] = event["frame_bytes"]
            elif direction == "REQUEST":
                row["gateway_request_receive_ns"] = event["actual_socket_receive_ns"]
            elif direction == "RESPONSE" and event.get("scheduled_send_ns"):
                row["gateway_response_scheduled_ns"] = event["scheduled_send_ns"]
                row["gateway_response_cutoff_ns"] = event["preparation_cutoff_ns"]
                row["gateway_response_prepared_ns"] = event["prepared_ns"]
                row["gateway_response_send_ns"] = event["actual_socket_send_ns"]
                row["response_bytes"] = event["frame_bytes"]
                row["destination"] = event["destination"]
            else:
                row["cloud_response_receive_ns"] = event["actual_socket_receive_ns"]
        rows = [merged[key] for key in sorted(merged)]
        required = {
            "cloud_request_scheduled_ns", "cloud_request_send_ns", "gateway_request_receive_ns",
            "gateway_response_scheduled_ns", "gateway_response_cutoff_ns", "gateway_response_prepared_ns",
            "gateway_response_send_ns", "cloud_response_receive_ns", "request_bytes", "response_bytes", "destination",
        }
        if len(rows) != expected or any(not required.issubset(row) for row in rows):
            raise AssertionError("incomplete V2 socket-boundary trace")
        if {row["request_bytes"] for row in rows} != {profile.frame_bytes} or {row["response_bytes"] for row in rows} != {profile.frame_bytes}:
            raise AssertionError("V2 fixed-size invariant failed")
        if {row["destination"] for row in rows} != {"CommonActionGatewayV2"}:
            raise AssertionError("V2 destination invariant failed")
        host_path = output / "host_visible_trace.jsonl"
        with host_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
        serialized = host_path.read_text(encoding="utf-8").lower()
        for forbidden in ("label", "provider", "operation_id", "private_", "result", "wait"):
            if forbidden in serialized:
                raise AssertionError(f"private field leaked to host trace: {forbidden}")
        return {
            "rows": len(rows), "worker_pid": worker.pid, "pacer_pid": pacer.pid, "client_pid": client.pid,
            "provider_pids": [process.pid for process in providers], "profile": asdict(profile),
        }
    finally:
        for process in providers:
            if process.poll() is None:
                process.terminate()
        for process in providers:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def continuation_sessions() -> tuple[list[dict[str, object]], list[EmulatorDefinition]]:
    sessions = [
        {"label": "FAST", "actions": [{"action": "TOOL", "provider": "FAST", "operation_id": "fast-op"}]},
        {"label": "SLOW", "actions": [{"action": "TOOL", "provider": "SLOW", "operation_id": "slow-op"}]},
    ]
    providers = [
        EmulatorDefinition("FAST", 15, 15),
        EmulatorDefinition("SLOW", 315, 315),
    ]
    return sessions, providers


def stress_sessions(repetitions: int = 3, real_actions: int = 50) -> tuple[list[dict[str, object]], list[EmulatorDefinition]]:
    definitions = [
        EmulatorDefinition("FAST", 2, 5, cpu_work_ms=0, background_workers=1),
        EmulatorDefinition("MEDIUM", 20, 40, cpu_work_ms=1, background_workers=1),
        EmulatorDefinition("SLOW", 80, 140, cpu_work_ms=3, background_workers=1),
        EmulatorDefinition("VERY_SLOW", 300, 500, cpu_work_ms=6, background_workers=1),
        EmulatorDefinition("JITTERED", 2, 500, cpu_work_ms=2, background_workers=1),
    ]
    sessions: list[dict[str, object]] = []
    for repetition in range(repetitions):
        for definition in definitions:
            actions = [
                {"action": "TOOL", "provider": definition.name, "operation_id": f"v2-{repetition}-{definition.name}-{slot}"}
                for slot in range(real_actions)
            ]
            sessions.append({"label": definition.name, "actions": actions})
    return sessions, definitions

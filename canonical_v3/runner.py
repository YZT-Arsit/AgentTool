from __future__ import annotations

import json
import multiprocessing
import os
import queue
import secrets
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from cloud_slot_proxy.proxy import ProxyConfig, run_cloud_slot_proxy
from privacy_kernel.control import ControlKernel
from privacy_kernel.protocol import CanonicalProfile, EnvelopeCodec, write_restricted_key


@dataclass(frozen=True)
class LocalProviderDefinition:
    name: str
    min_delay_ms: int
    max_delay_ms: int
    effectful: bool = False
    cpu_work_ms: int = 0


DEFAULT_PROVIDERS = (
    LocalProviderDefinition("LOCAL_MODEL", 2, 4),
    LocalProviderDefinition("READ_ONLY_TOOL", 3, 5),
    LocalProviderDefinition("EFFECTFUL_TOOL", 3, 5, effectful=True),
)


def _go(root: Path) -> Path:
    bundled = root / ".toolchains/go/Go/bin/go.exe"
    if bundled.exists():
        return bundled
    system = shutil.which("go")
    if system is None:
        raise FileNotFoundError("Go toolchain is unavailable")
    return Path(system)


def _build_canonical_binaries(root: Path) -> dict[str, Path]:
    """Build only trusted Gateway roles; the legacy private client is excluded."""
    module = root / "common_action_gateway_v2"
    output = module / "bin"
    output.mkdir(exist_ok=True)
    suffix = ".exe" if os.name == "nt" else ""
    commands = {"worker": "gateway-worker", "pacer": "gateway-pacer",
                "provider": "local-provider-emulator"}
    binaries: dict[str, Path] = {}
    for role, command in commands.items():
        target = output / f"{command}{suffix}"
        subprocess.run([str(_go(root)), "build", "-o", str(target), f"./cmd/{command}"],
                       cwd=module, check=True)
        binaries[role] = target
    return binaries


def _read_ready(process: subprocess.Popen[str], timeout: float = 10.0) -> str:
    messages: queue.Queue[str] = queue.Queue(maxsize=1)
    thread = threading.Thread(target=lambda: messages.put(
        process.stdout.readline().strip() if process.stdout else ""), daemon=True)
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


def _affinity_plan() -> tuple[int, int, int]:
    cpus = os.cpu_count() or 1
    if cpus >= 3:
        return 0, 1, 2
    if cpus == 2:
        return 0, 1, 1
    return -1, -1, -1


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run_canonical_gateway(root: Path, output: Path, profile: CanonicalProfile,
                          kernel: ControlKernel,
                          providers: tuple[LocalProviderDefinition, ...] = DEFAULT_PROVIDERS) -> dict[str, object]:
    """Execute the canonical trusted-kernel -> opaque-proxy -> Gateway path."""
    root, output = root.resolve(), output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing canonical result: {output}")
    output.mkdir(parents=True, exist_ok=True)
    binaries = _build_canonical_binaries(root)
    public_profile = output / "public_profile.json"
    _write_json(public_profile, profile.as_public_dict())
    key = secrets.token_bytes(16)
    key_file = output / "trusted_gateway.key"
    write_restricted_key(key_file, key)
    codec = EnvelopeCodec(key, profile)
    pacer_cpu, worker_cpu, _ = _affinity_plan()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    provider_processes: list[subprocess.Popen[str]] = []
    worker: subprocess.Popen[str] | None = None
    pacer: subprocess.Popen[str] | None = None
    proxy: multiprocessing.Process | None = None
    try:
        endpoints: dict[str, str] = {}
        effectful: dict[str, bool] = {}
        for ordinal, definition in enumerate(providers):
            command = [
                str(binaries["provider"]), "--listen", "127.0.0.1:0", "--name", definition.name,
                "--min-delay-ms", str(definition.min_delay_ms), "--max-delay-ms", str(definition.max_delay_ms),
                "--cpu-work-ms", str(definition.cpu_work_ms), "--seed", str(8100 + ordinal),
                "--cpu", str(worker_cpu),
            ]
            if definition.effectful:
                command.append("--effectful")
            process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, creationflags=hidden)
            provider_processes.append(process)
            endpoints[definition.name] = _read_ready(process).split()[1]
            effectful[definition.name] = definition.effectful
        private_provider_config = output / "trusted_provider_config.json"
        _write_json(private_provider_config, {"endpoints": endpoints, "effectful": effectful,
                                              "timeout_ms": 2000, "allow_generic_http": False})
        total = profile.sessions * profile.slots
        request_ring = output / "request_ring.shared"
        result_ring = output / "result_ring.shared"
        worker = subprocess.Popen([
            str(binaries["worker"]), "--request-ring", str(request_ring), "--result-ring", str(result_ring),
            "--capacity", str(max(1024, total * 2)), "--frame-bytes", str(profile.frame_bytes),
            "--expected-frames", str(total), "--key-file", str(key_file), "--profile", str(public_profile),
            "--providers", str(private_provider_config), "--private-log", str(output / "trusted_worker.jsonl"),
            "--cpu", str(worker_cpu),
        ], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=hidden)
        worker_ready = _read_ready(worker)
        pacer = subprocess.Popen([
            str(binaries["pacer"]), "--listen", "127.0.0.1:0", "--profile", str(public_profile),
            "--request-ring", str(request_ring), "--result-ring", str(result_ring),
            "--key-file", str(key_file), "--host-log", str(output / "gateway_public_boundary.jsonl"),
            "--private-log", str(output / "trusted_delivery.jsonl"),
            "--status", str(output / "gateway_status.json"), "--cpu", str(pacer_cpu),
        ], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=hidden)
        pacer_ready = _read_ready(pacer)
        address = pacer_ready.split()[1]

        context = multiprocessing.get_context("spawn")
        requests = context.Queue(maxsize=max(8, profile.slots * 2))
        responses = context.Queue(maxsize=max(8, profile.slots * 2))
        readiness = context.Queue(maxsize=1)
        proxy_config = ProxyConfig(address, profile, output / "agentcloud_public_trace.jsonl")
        proxy = context.Process(target=run_cloud_slot_proxy,
                                args=(proxy_config, requests, responses, readiness),
                                name="cloud-slot-proxy")
        proxy.start()
        public_ready = readiness.get(timeout=15)
        if not public_ready.get("ready"):
            raise RuntimeError("Cloud Slot Proxy did not become ready")

        trusted_trace: list[dict[str, object]] = []
        delivered_results = 0
        for session in range(profile.sessions):
            descriptor = kernel.tick()
            for slot in range(1, profile.slots + 1):
                if slot == 1 and descriptor is not None:
                    frame = codec.encode_request(session, slot, action=descriptor.action,
                                                 provider=descriptor.provider,
                                                 operation_id=descriptor.operation_id,
                                                 payload=descriptor.payload)
                else:
                    frame = codec.encode_noop(session, slot)
                requests.put(frame, timeout=10)
            accepted = False
            for _ in range(profile.slots):
                decoded = codec.decode_response(responses.get(timeout=30))
                if decoded is not None:
                    delivered_results += 1
                    accepted = kernel.accept_result(decoded) or accepted
            trusted_trace.append({
                "session": session, "private_opcode": kernel.ticks[-1].private_opcode,
                "emitted_action": descriptor is not None, "accepted_result": accepted,
                "logical_agent_id": kernel.state.logical_agent_id,
                "returned": kernel.state.returned,
            })

        proxy.join(timeout=30)
        if proxy.exitcode != 0:
            raise RuntimeError(f"Cloud Slot Proxy failed with exit code {proxy.exitcode}")
        pacer_stdout, pacer_stderr = pacer.communicate(timeout=20)
        if pacer.returncode:
            raise RuntimeError(f"Gateway Pacer failed: {pacer_stderr}")
        worker_stdout, worker_stderr = worker.communicate(timeout=20)
        if worker.returncode:
            raise RuntimeError(f"Gateway Worker failed: {worker_stderr}")

        with (output / "privacy_kernel_private_trace.jsonl").open("w", encoding="utf-8") as handle:
            for row in trusted_trace:
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
        public_rows = _jsonl(output / "agentcloud_public_trace.jsonl")
        if len(public_rows) != total * 2:
            raise AssertionError("Cloud observer did not see the fixed bidirectional schedule")
        serialized_public = json.dumps(public_rows, separators=(",", ":")).lower()
        for forbidden in ("logical_agent", "provider", "operation_id", "opcode", "payload", "result", "key"):
            if forbidden in serialized_public:
                raise AssertionError(f"private value leaked to O_agentcloud: {forbidden}")
        worker_rows = _jsonl(output / "trusted_worker.jsonl")
        summary = next(row for row in worker_rows if row.get("kind") == "SUMMARY")
        result = {
            "profile_id": profile.profile_id, "public_frames_each_direction": total,
            "delivered_results": delivered_results, "returned": kernel.state.returned,
            "logical_agent_id_private": kernel.state.logical_agent_id,
            "real_heavy_operations": int(summary["real_operations"]),
            "dummy_heavy_operations": int(summary["dummy_heavy_ops"]),
            "effect_count": sum(bool(row.get("effect")) for row in worker_rows),
            "worker_pid": worker.pid, "pacer_pid": pacer.pid, "proxy_pid": proxy.pid,
            "provider_pids": [process.pid for process in provider_processes],
            "one_persistent_tunnel": True, "key_on_command_line": False,
        }
        _write_json(output / "canonical_run_summary.json", result)
        _write_json(output / "process_output.json", {
            "worker_ready": worker_ready, "pacer_ready": pacer_ready,
            "worker_stdout": worker_stdout, "worker_stderr": worker_stderr,
            "pacer_stdout": pacer_stdout, "pacer_stderr": pacer_stderr,
        })
        return result
    finally:
        if key_file.exists():
            key_file.unlink()
        for process in (proxy, pacer, worker, *provider_processes):
            if process is None:
                continue
            if isinstance(process, multiprocessing.Process):
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
            elif process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

from __future__ import annotations

import json
import os
import queue
import secrets
import shutil
import subprocess
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from privacy_kernel.protocol import ACTION_NOOP, ACTION_TOOL, CanonicalProfile, EnvelopeCodec


@dataclass(frozen=True)
class V7FunctionalProfile:
    name: str
    real_operations: int
    frame_bytes: int = 1024
    request_delta_ns: int = 2_000_000
    response_delta_ns: int = 10_000_000
    mask_ns: int = 2_000_000
    start_delay_ns: int = 100_000_000
    provider_completion_bound_ns: int = 800_000_000
    terminal_slots: int = 1

    @property
    def completion_slots(self) -> int:
        return (self.provider_completion_bound_ns + self.response_delta_ns - 1) // self.response_delta_ns

    @property
    def slots(self) -> int:
        # Leading admission cells + completion tail + worst-case one-result-per-cell drain + terminal.
        return self.real_operations + self.completion_slots + self.real_operations + self.terminal_slots

    def wire(self) -> dict[str, object]:
        return {
            "name": self.name,
            "frame_bytes": self.frame_bytes,
            "slots": self.slots,
            "sessions": 1,
            "request_delta_ns": self.request_delta_ns,
            "response_delta_ns": self.response_delta_ns,
            "mask_ns": self.mask_ns,
            "start_delay_ns": self.start_delay_ns,
            "inter_session_gap_ns": 0,
        }

    def admission(self) -> dict[str, object]:
        return {
            "sessions": 1,
            "slots_per_session": self.slots,
            "admission_slots": self.real_operations,
            "max_real_operations": self.real_operations,
            "slot_interval_ns": self.response_delta_ns,
            "provider_completion_bound_ns": self.provider_completion_bound_ns,
            "terminal_slots": self.terminal_slots,
        }


def _go(root: Path) -> str:
    candidates = [
        root / ".toolchains/go/Go/bin/go.exe",
        Path("/root/autodl-tmp/toolchains/go/bin/go"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    found = shutil.which("go")
    if not found:
        raise FileNotFoundError("Go toolchain not found")
    return found


def build_binaries(root: Path) -> dict[str, Path]:
    module = root / "common_action_gateway_v2"
    output = module / "bin_v7"
    output.mkdir(exist_ok=True)
    suffix = ".exe" if os.name == "nt" else ""
    commands = {
        "worker": "gateway-worker-v7",
        "pacer": "gateway-pacer-v7",
        "client": "gateway-cloud-client",
        "provider": "local-provider-emulator",
    }
    binaries: dict[str, Path] = {}
    for role, command in commands.items():
        target = output / f"{command}{suffix}"
        subprocess.run([_go(root), "build", "-o", str(target), f"./cmd/{command}"], cwd=module, check=True)
        binaries[role] = target
    return binaries


def _read_ready(process: subprocess.Popen[str], timeout: float = 15.0) -> str:
    messages: queue.Queue[str] = queue.Queue()

    def read() -> None:
        messages.put(process.stdout.readline().strip() if process.stdout else "")

    threading.Thread(target=read, daemon=True).start()
    try:
        line = messages.get(timeout=timeout)
    except queue.Empty as exc:
        process.terminate()
        raise RuntimeError("process readiness timeout") from exc
    if not line.startswith("READY"):
        stderr = process.stderr.read() if process.stderr else ""
        raise RuntimeError(f"process failed readiness: {line!r} {stderr}")
    return line


def _write(path: Path, value: object, *, mode: int | None = None) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def run_functional_gate(
    root: Path,
    output: Path,
    profile: V7FunctionalProfile,
    *,
    provider_sequence: list[str] | None = None,
    operation_prefix: str = "v7-functional",
) -> dict[str, object]:
    """Run the V7 functional gate with real local HTTP provider I/O.

    The cloud process receives opaque fixed-width frames only. Results are
    decoded and deduplicated in this trusted orchestration boundary.
    """

    root, output = root.resolve(), output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    binaries = build_binaries(root)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    wire_path = output / "public_profile.json"
    admission_path = output / "admission_profile.json"
    _write(wire_path, profile.wire())
    _write(admission_path, profile.admission())
    key_bytes = secrets.token_bytes(16)
    key_path = output / ".private_gateway_key"
    key_path.write_text(key_bytes.hex(), encoding="ascii")
    key_path.chmod(0o600)

    provider_definitions = [
        ("FAST", 2, 5),
        ("MEDIUM", 20, 40),
        ("SLOW", 80, 140),
        ("JITTERED", 2, 450),
    ]
    providers: list[subprocess.Popen[str]] = []
    processes: list[subprocess.Popen[str]] = []
    try:
        endpoints: dict[str, str] = {}
        for index, (name, minimum, maximum) in enumerate(provider_definitions):
            process = subprocess.Popen(
                [str(binaries["provider"]), "--listen", "127.0.0.1:0", "--name", name,
                 "--min-delay-ms", str(minimum), "--max-delay-ms", str(maximum),
                 "--seed", str(8100 + index), "--cpu", "-1", "--effectful"],
                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=hidden,
            )
            providers.append(process)
            endpoints[name] = _read_ready(process).split()[1]
        provider_path = output / "private_provider_config.json"
        _write(provider_path, {
            "endpoints": endpoints,
            "effect_semantics": {name: "IDEMPOTENT_EFFECT" for name in endpoints},
            "timeout_ms": 700,
            "allow_generic_http": False,
        })

        actions = []
        provider_codes = {"FAST": 1, "MEDIUM": 2, "SLOW": 3, "JITTERED": 5}
        names = [definition[0] for definition in provider_definitions]
        if provider_sequence is not None and len(provider_sequence) != profile.real_operations:
            raise ValueError("provider sequence length must equal real-operation count")
        for index in range(profile.real_operations):
            provider = provider_sequence[index] if provider_sequence is not None else names[index % len(names)]
            if provider not in provider_codes:
                raise ValueError(f"unknown local provider class: {provider}")
            actions.append({"provider": provider, "operation_id": f"{operation_prefix}-{index}"})
        _write(output / "private_workload.json", {"sessions": [{"label": "MIXED", "actions": [
            {"action": "TOOL", **action} for action in actions
        ]}]})

        canonical = CanonicalProfile(**profile.wire())
        codec = EnvelopeCodec(key_bytes, canonical)
        frames: list[bytes] = []
        for slot in range(1, profile.slots + 1):
            if slot <= len(actions):
                action = actions[slot - 1]
                frames.append(codec.encode_request(0, slot, action=ACTION_TOOL,
                    provider=provider_codes[action["provider"]], operation_id=action["operation_id"], payload=b"v7"))
            else:
                frames.append(codec.encode_request(0, slot, action=ACTION_NOOP, provider=0,
                    operation_id=f"pad-{slot}", payload=b""))
        opaque_requests = output / "trusted_pre_encrypted_frames.bin"
        opaque_requests.write_bytes(b"".join(frames))

        request_ring, result_ring = output / "request_ring.shared", output / "result_ring.shared"
        worker_done = output / "worker_done.json"
        worker = subprocess.Popen(
            [str(binaries["worker"]), "--request-ring", str(request_ring), "--result-ring", str(result_ring),
             "--capacity", str(max(4096, profile.slots * 2)), "--frame-bytes", str(profile.frame_bytes),
             "--expected-frames", str(profile.slots), "--key-file", str(key_path), "--providers", str(provider_path),
             "--profile", str(wire_path), "--private-log", str(output / "worker_private.jsonl"),
             "--operation-journal", str(output / "operation_journal.json"), "--worker-done", str(worker_done)],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=hidden,
        )
        processes.append(worker)
        _read_ready(worker)
        pacer = subprocess.Popen(
            [str(binaries["pacer"]), "--listen", "127.0.0.1:0", "--profile", str(wire_path),
             "--admission-profile", str(admission_path), "--request-ring", str(request_ring),
             "--result-ring", str(result_ring), "--ready-queue", str(output / "durable_ready_queue.json"),
             "--worker-done", str(worker_done), "--key-file", str(key_path),
             "--host-log", str(output / "pacer_socket_boundary.jsonl"),
             "--private-log", str(output / "pacer_private_delivery.jsonl"),
             "--lifecycle", str(output / "pacer_lifecycle.csv"), "--status", str(output / "pacer_status.json")],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=hidden,
        )
        processes.append(pacer)
        address = _read_ready(pacer).split()[1]
        opaque_responses = output / "opaque_response_frames.bin"
        client = subprocess.Popen(
            [str(binaries["client"]), "--address", address, "--profile", str(wire_path),
             "--opaque-frames", str(opaque_requests), "--opaque-responses", str(opaque_responses),
             "--host-log", str(output / "cloud_socket_boundary.jsonl")],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=hidden,
        )
        processes.append(client)
        timeout = max(30.0, profile.slots * profile.response_delta_ns / 1e9 * 3 + 15)
        for name, process in (("client", client), ("pacer", pacer), ("worker", worker)):
            stdout, stderr = process.communicate(timeout=timeout)
            if process.returncode:
                raise RuntimeError(f"{name} failed: {stderr}")

        raw = opaque_responses.read_bytes()
        if len(raw) != profile.slots * profile.frame_bytes:
            raise AssertionError("response transcript length mismatch")
        decoded, duplicate_results = {}, 0
        terminal_status = None
        for offset in range(0, len(raw), profile.frame_bytes):
            result = codec.decode_response(raw[offset:offset + profile.frame_bytes])
            if result is None:
                continue
            if result.operation_id == "__gateway_profile_status__":
                terminal_status = result.payload.decode(errors="replace")
                continue
            if result.operation_id in decoded:
                duplicate_results += 1
                continue
            decoded[result.operation_id] = result
        admitted_ids = {action["operation_id"] for action in actions}
        missing = sorted(admitted_ids - decoded.keys())
        unexpected = sorted(decoded.keys() - admitted_ids)
        worker_rows = [json.loads(line) for line in (output / "worker_private.jsonl").read_text().splitlines() if line]
        worker_events = [row for row in worker_rows if row.get("operation_id")]
        real_effects = sum(bool(row.get("effect")) for row in worker_events)
        summary = next(row for row in worker_rows if row.get("kind") == "SUMMARY")
        status = json.loads((output / "pacer_status.json").read_text())
        result = {
            "profile": asdict(profile),
            "admitted_operations": len(admitted_ids),
            "unique_framework_results": len(decoded),
            "missing_operation_ids": missing,
            "unexpected_operation_ids": unexpected,
            "duplicate_framework_results_suppressed": duplicate_results,
            "worker_real_operations": summary["real_operations"],
            "real_effects": real_effects,
            "dummy_heavy_ops": summary["dummy_heavy_ops"],
            "terminal_status": terminal_status or status["terminal_status"],
            "fixed_frames": profile.slots,
            "functional_pass": not missing and not unexpected and len(decoded) == len(admitted_ids)
                and summary["real_operations"] == len(admitted_ids) and real_effects == len(admitted_ids)
                and summary["dummy_heavy_ops"] == 0 and terminal_status is None,
        }
        _write(output / "functional_summary.json", result)
        return result
    finally:
        for process in processes + providers:
            if process.poll() is None:
                process.terminate()
        for process in processes + providers:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if key_path.exists():
            key_path.unlink()

from __future__ import annotations

import base64
import csv
import json
import os
import random
import socket
import subprocess
import time
import ctypes
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


REQUEST_AAD = b"ACV_TIMING_REQ_V1"


@dataclass(frozen=True)
class ActionSpec:
    action: str
    provider: str
    latency_ms: float


@dataclass(frozen=True)
class EpisodeSpec:
    token: int
    family: str
    label: str
    actions: tuple[ActionSpec, ...]


@dataclass(frozen=True)
class PublicProfile:
    name: str
    slots: int
    delta_ms: float
    response_lag_ms: float
    frame_bytes: int = 1024
    start_delay_ms: float = 25.0
    inter_episode_ms: float = 5.0


def latency_for(provider: str, rng: random.Random) -> float:
    ranges = {
        "FAST": (10.0, 25.0),
        "MEDIUM": (100.0, 250.0),
        "SLOW": (500.0, 1000.0),
        "VERY_SLOW": (1500.0, 3000.0),
        "JITTERED": (10.0, 1000.0),
        "NONE": (0.0, 0.0),
    }
    low, high = ranges[provider]
    return rng.uniform(low, high)


def _encrypted_frame(key: bytes, profile: PublicProfile, token: int, slot: int, spec: ActionSpec) -> bytes:
    aes = AESGCM(key)
    payload = json.dumps({
        "episode_token": token,
        "slot": slot,
        "action": spec.action,
        "provider": spec.provider,
        "latency_ms": spec.latency_ms,
        "operation_id": f"op-{token:x}-{slot}",
    }, separators=(",", ":")).encode("utf-8")
    plaintext_bytes = profile.frame_bytes - 8 - 12 - 16
    if len(payload) > plaintext_bytes:
        raise ValueError("timing request exceeds fixed frame")
    plaintext = payload + b"\0" * (plaintext_bytes - len(payload))
    nonce = os.urandom(12)
    return b"\0" * 8 + nonce + aes.encrypt(nonce, plaintext, REQUEST_AAD)


def build_workload(profile: PublicProfile, episodes: list[EpisodeSpec], key: bytes, output: Path) -> None:
    rows = []
    for episode in episodes:
        if len(episode.actions) > profile.slots:
            raise ValueError("episode exceeds public slot horizon")
        padded = list(episode.actions) + [ActionSpec("NOOP", "NONE", 0.0)] * (profile.slots - len(episode.actions))
        rows.append({
            "token": episode.token,
            "frames_base64": [base64.b64encode(_encrypted_frame(key, profile, episode.token, index + 1, spec)).decode("ascii")
                              for index, spec in enumerate(padded)],
        })
    output.write_text(json.dumps({
        "frame_bytes": profile.frame_bytes,
        "delta_ns": int(profile.delta_ms * 1e6),
        "response_lag_ns": int(profile.response_lag_ms * 1e6),
        "start_delay_ns": int(profile.start_delay_ms * 1e6),
        "inter_episode_ns": int(profile.inter_episode_ms * 1e6),
        "public_profile": profile.name,
        "episodes": rows,
    }, separators=(",", ":")), encoding="utf-8")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _process_metrics(process: subprocess.Popen[str]) -> dict[str, float | int]:
    if os.name != "nt":
        return {"cpu_seconds": -1.0, "peak_working_set_bytes": -1}
    class FileTime(ctypes.Structure):
        _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]
    class Memory(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    creation = FileTime(); exit_time = FileTime(); kernel = FileTime(); user = FileTime()
    handle = ctypes.c_void_p(int(process._handle))  # type: ignore[attr-defined]
    ctypes.windll.kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                           ctypes.byref(kernel), ctypes.byref(user))
    memory = Memory(); memory.cb = ctypes.sizeof(memory)
    ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb)
    ticks = lambda value: (int(value.high) << 32) | int(value.low)
    return {"cpu_seconds": (ticks(kernel) + ticks(user)) / 10_000_000,
            "peak_working_set_bytes": int(memory.PeakWorkingSetSize)}


def run_native_gateway(root: Path, profile: PublicProfile, episodes: list[EpisodeSpec], output: Path) -> list[dict[str, object]]:
    root = root.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    key = AESGCM.generate_key(bit_length=128)
    workload = output / "encrypted_public_workload.json"
    build_workload(profile, episodes, key, workload)
    truth_path = output / "private_ground_truth.csv"
    with truth_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("episode_token", "family", "label", "real_actions", "real_heavy_ops"))
        writer.writeheader()
        for episode in episodes:
            writer.writerow({"episode_token": episode.token, "family": episode.family, "label": episode.label,
                             "real_actions": len(episode.actions),
                             "real_heavy_ops": sum(spec.action in {"LLM", "TOOL"} for spec in episode.actions)})
    executable = root / "timing_closure_native" / "timing-closure.exe"
    port = _free_port()
    gateway_host = output / "gateway_socket_boundary.jsonl"
    gateway_private = output / "gateway_private_instrumentation.jsonl"
    cloud_host = output / "cloud_socket_boundary.jsonl"
    gateway = subprocess.Popen([
        str(executable), "--mode", "gateway", "--port", str(port), "--key", key.hex(),
        "--host-log", str(gateway_host), "--private-log", str(gateway_private),
        "--frame-bytes", str(profile.frame_bytes),
    ], cwd=root / "timing_closure_native", stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    ready = gateway.stdout.readline().strip() if gateway.stdout else ""
    if not ready.startswith("READY "):
        stderr = gateway.stderr.read() if gateway.stderr else ""
        raise RuntimeError(f"gateway did not start: {ready} {stderr}")
    address = ready.split(" ", 1)[1]
    client = subprocess.Popen([
        str(executable), "--mode", "client", "--address", address,
        "--workload", str(workload), "--host-log", str(cloud_host),
    ], cwd=root / "timing_closure_native", text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    client_stdout, client_stderr = client.communicate(
        timeout=max(60, int(len(episodes) * profile.slots * profile.delta_ms / 1000 * 2 + 30)))
    client_metrics = _process_metrics(client)
    (output / "client_stdout.txt").write_text(client_stdout, encoding="utf-8")
    (output / "client_stderr.txt").write_text(client_stderr, encoding="utf-8")
    if client.returncode:
        gateway.terminate()
        raise RuntimeError(f"native client failed: {client_stderr}")
    gateway.wait(timeout=30)
    gateway_metrics = _process_metrics(gateway)
    gateway_stderr = gateway.stderr.read() if gateway.stderr else ""
    (output / "gateway_stderr.txt").write_text(gateway_stderr, encoding="utf-8")
    if gateway.returncode:
        raise RuntimeError(f"native gateway failed: {gateway_stderr}")
    (output / "process_metrics.json").write_text(json.dumps({
        "cloud_pacer": client_metrics, "gateway": gateway_metrics,
    }, indent=2), encoding="utf-8")

    merged: dict[tuple[int, int], dict[str, object]] = {}
    for path in (cloud_host, gateway_host):
        for row in _jsonl(path):
            key_tuple = (int(row["episode_token"]), int(row["slot"]))
            merged.setdefault(key_tuple, {"episode_token": key_tuple[0], "slot": key_tuple[1]}).update(row)
    rows = [merged[key] for key in sorted(merged)]
    expected = len(episodes) * profile.slots
    if len(rows) != expected or any(len([k for k in row if k.endswith("_ns")]) < 4 for row in rows):
        raise AssertionError("incomplete bidirectional socket-boundary trace")
    if any(int(row["request_bytes"]) != profile.frame_bytes or int(row["response_bytes"]) != profile.frame_bytes for row in rows):
        raise AssertionError("fixed frame invariant failed")
    host_path = output / "host_visible_trace.jsonl"
    with host_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    forbidden = ('"private_', '"action"', '"provider"', '"latency_ms"', '"operation_id"', '"label"')
    serialized = host_path.read_text(encoding="utf-8").lower()
    if any(value in serialized for value in forbidden):
        raise AssertionError("private field entered host-visible trace")
    return rows

from __future__ import annotations

import csv
import json
import os
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agent_control_virtualization.experiment import compile_frameworks
from agent_control_virtualization.ir import AgentCapsule, CAPSULE_BYTES


SIMPLEPIR_COMMIT = "e9020b03bf2872c75b8954e749e32408b5db87ed"


@dataclass(frozen=True)
class PIRRequest:
    episode: str
    round: int
    index: int
    private_class: str


@dataclass(frozen=True)
class SimplePIRArtifacts:
    metrics: dict[str, object]
    client_trace: list[dict[str, object]]
    server_trace: list[dict[str, object]]
    recovered: list[bytes]
    raw_query_path: Path


def prototype_capsules() -> tuple[bytes, ...]:
    return tuple(capsule.serialize() for result in compile_frameworks() for capsule in result.capsules)


def generate_registry(path: Path, record_count: int) -> str:
    """Create exactly `record_count` fixed rows from real-framework prototypes."""
    import hashlib

    path.parent.mkdir(parents=True, exist_ok=True)
    prototypes = prototype_capsules()
    digest = hashlib.sha256()
    with path.open("wb") as handle:
        for index in range(record_count):
            row = bytearray(prototypes[index % len(prototypes)])
            struct.pack_into("!I", row, 8, index)
            handle.write(row)
            digest.update(row)
    if path.stat().st_size != record_count * CAPSULE_BYTES:
        raise AssertionError("registry was not fully instantiated")
    return digest.hexdigest()


def write_requests(path: Path, requests: list[PIRRequest]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("episode", "round", "index", "class"))
        writer.writerows((item.episode, item.round, item.index, item.private_class) for item in requests)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run_simplepir(
    root: Path,
    registry: Path,
    record_count: int,
    requests: list[PIRRequest],
    output_dir: Path,
    *,
    paced_delta_ms: float = 0.0,
    paced_start_delay_ms: float = 20.0,
) -> SimplePIRArtifacts:
    root = root.resolve()
    registry = registry.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    query_path = output_dir / "private_queries.csv"
    write_requests(query_path, requests)
    metrics_path = output_dir / "metrics.json"
    client_path = output_dir / "client_private_trace.jsonl"
    server_path = output_dir / "server_visible_trace.jsonl"
    recovered_path = output_dir / "client_recovered_records.jsonl"
    raw_path = output_dir / "server_raw_queries.bin"
    bridge_dir = root / "pir_integration" / "simplepir_bridge"
    env = dict(os.environ)
    if os.name == "nt":
        go_executable = root / ".toolchains" / "go" / "Go" / "bin" / "go.exe"
        if not go_executable.exists():
            raise FileNotFoundError("project-local Windows Go toolchain is missing")
        gcc_bin = root / ".toolchains" / "winlibs" / "mingw64" / "bin"
        env["PATH"] = (str(go_executable.parent) + os.pathsep + str(gcc_bin)
                       + os.pathsep + env.get("PATH", ""))
        compiler = gcc_bin / "gcc.exe"
    else:
        discovered_go = shutil.which("go")
        discovered_cc = shutil.which("gcc")
        if discovered_go is None or discovered_cc is None:
            raise FileNotFoundError("Linux SimplePIR integration requires Go and gcc on PATH")
        go_executable = Path(discovered_go)
        compiler = Path(discovered_cc)
    env["CGO_ENABLED"] = "1"
    env["CC"] = str(compiler)
    command = [
        str(go_executable), "run", ".", "--database", str(registry), "--records", str(record_count),
        "--queries", str(query_path), "--metrics", str(metrics_path),
        "--client-trace", str(client_path), "--server-trace", str(server_path),
        "--recovered", str(recovered_path), "--raw-queries", str(raw_path),
        "--commit", SIMPLEPIR_COMMIT,
    ]
    if paced_delta_ms > 0:
        command.extend(["--paced-delta-ms", str(paced_delta_ms),
                        "--paced-start-delay-ms", str(paced_start_delay_ms)])
    completed = subprocess.run(command, cwd=bridge_dir, env=env, check=True,
                               text=True, capture_output=True)
    (output_dir / "bridge_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "bridge_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    client = _jsonl(client_path)
    server = _jsonl(server_path)
    recovered_rows = _jsonl(recovered_path)
    import base64
    recovered = [base64.b64decode(item["record_base64"]) for item in recovered_rows]
    if not all(len(row) == CAPSULE_BYTES for row in recovered):
        raise AssertionError("PIR returned malformed capsule")
    forbidden = ("private_index", "private_class", "agent_name", "logical_agent")
    encoded_server = server_path.read_text(encoding="utf-8").lower()
    if any(field in encoded_server for field in forbidden):
        raise AssertionError("private field entered server-visible trace")
    return SimplePIRArtifacts(json.loads(metrics_path.read_text(encoding="utf-8")),
                              client, server, recovered, raw_path)


def read_raw_queries(path: Path) -> list[bytes]:
    values: list[bytes] = []
    with path.open("rb") as handle:
        while True:
            header = handle.read(8)
            if not header:
                break
            if len(header) != 8:
                raise ValueError("truncated query log")
            size = struct.unpack("<Q", header)[0]
            payload = handle.read(size)
            if len(payload) != size:
                raise ValueError("truncated query payload")
            values.append(payload)
    return values


def recovered_capsules(artifacts: SimplePIRArtifacts) -> list[AgentCapsule]:
    return [AgentCapsule.deserialize(payload) for payload in artifacts.recovered]

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .artifact import PIR_RECORD_BYTES


SIMPLEPIR_COMMIT = "e9020b03bf2872c75b8954e749e32408b5db87ed"


@dataclass(frozen=True)
class SimplePIRResult:
    row: bytes
    query_bytes: int
    answer_bytes: int
    query_sha256: str
    correct: bool


class PersistentSimplePIRArtifactClient:
    """Trusted-side client of the existing real interactive SimplePIR bridge."""

    production_ready = True

    def __init__(
        self,
        bridge_binary: Path,
        database: Path,
        record_count: int,
        output: Path,
        *,
        expected_sha256: str | None = None,
    ):
        bridge_binary = bridge_binary.resolve()
        database = database.resolve()
        output = output.resolve()
        if record_count <= 0 or database.stat().st_size != record_count * PIR_RECORD_BYTES:
            raise ValueError("SimplePIR database does not match fixed record count/width")
        digest = hashlib.sha256(bridge_binary.read_bytes()).hexdigest()
        if expected_sha256 and digest != expected_sha256.lower():
            raise RuntimeError("SimplePIR binary hash mismatch")
        output.mkdir(parents=True, exist_ok=False)
        self.binary_sha256 = digest
        self.record_count = record_count
        self.process = subprocess.Popen(
            [
                str(bridge_binary),
                "--interactive",
                "--database", str(database),
                "--records", str(record_count),
                "--metrics", str(output / "metrics.json"),
                "--client-trace", str(output / "client_private_trace.jsonl"),
                "--server-trace", str(output / "server_visible_trace.jsonl"),
                "--commit", SIMPLEPIR_COMMIT,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=(output / "bridge_stderr.txt").open("wb"),
            text=True,
            bufsize=1,
        )
        assert self.process.stdout is not None
        startup_lines: list[str] = []
        ready = None
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(
                    "SimplePIR exited before PIR_READY; startup output: "
                    + " | ".join(startup_lines[-8:])
                )
            startup_lines.append(line.rstrip())
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if candidate.get("type") == "PIR_READY":
                ready = candidate
                break
        if int(ready.get("records", -1)) != record_count:
            raise RuntimeError("SimplePIR did not enter the expected ready state")
        (output / "startup_stdout.txt").write_text(
            "\n".join(startup_lines) + "\n", encoding="utf-8"
        )
        (output / "preprocessing_ready.json").write_text(
            json.dumps(ready, indent=2) + "\n", encoding="utf-8"
        )
        self._ordinal = 0

    def query(self, operation_id: str, row_index: int) -> SimplePIRResult:
        if not operation_id or not 0 <= row_index < self.record_count:
            raise ValueError("invalid SimplePIR query")
        if self.process.poll() is not None:
            raise RuntimeError("SimplePIR bridge is not running")
        assert self.process.stdin is not None and self.process.stdout is not None
        request = {"operation_id": operation_id, "index": row_index, "ordinal": self._ordinal}
        self._ordinal += 1
        self.process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        response = json.loads(self.process.stdout.readline())
        if response.get("type") != "PIR_RESULT" or response.get("operation_id") != operation_id:
            raise RuntimeError(f"SimplePIR query failed: {response}")
        row = base64.b64decode(response["record_base64"])
        if len(row) != PIR_RECORD_BYTES:
            raise RuntimeError("SimplePIR returned the wrong record width")
        return SimplePIRResult(
            row=row,
            query_bytes=int(response["query_bytes"]),
            answer_bytes=int(response["answer_bytes"]),
            query_sha256=str(response["query_sha256"]),
            correct=bool(response["correct"]),
        )

    def close(self) -> None:
        if self.process.poll() is None:
            assert self.process.stdin is not None
            self.process.stdin.close()
            try:
                self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=10)

    def __enter__(self) -> "PersistentSimplePIRArtifactClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def require_real_simplepir(value: object) -> None:
    if not isinstance(value, PersistentSimplePIRArtifactClient) or not value.production_ready:
        raise RuntimeError("REAL_SIMPLEPIR_REQUIRED: mock retrieval is forbidden")

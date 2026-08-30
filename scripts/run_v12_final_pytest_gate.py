from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("serial", "default"), default="serial")
    parser.add_argument("--prepend-path", default="")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    nodes = manifest["nodes"]
    if len(nodes) != manifest["node_count"] or len({row["node_id"] for row in nodes}) != len(nodes):
        raise RuntimeError("invalid frozen pytest manifest")
    for row in nodes:
        path = ROOT / row["source_path"]
        if sha256(path) != row["source_sha256"]:
            raise RuntimeError(f"frozen test source mismatch: {row['source_path']}")

    env = os.environ.copy()
    if args.prepend_path:
        env["PATH"] = args.prepend_path + os.pathsep + env.get("PATH", "")
    command = [sys.executable, "-m", "pytest", "-q"]
    if args.mode == "serial":
        command.extend(("-p", "no:xdist"))
    command.extend(row["node_id"] for row in nodes)
    started_ns = time.monotonic_ns()
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env)
    ended_ns = time.monotonic_ns()
    raw_path = output / "pytest.txt"
    raw_path.write_text(completed.stdout + completed.stderr, encoding="utf-8", newline="\n")
    result = {
        "schema": "AgentTool.V12Final.PytestGate/1",
        "mode": args.mode,
        "manifest_sha256": sha256(manifest_path),
        "node_count": len(nodes),
        "exit_code": completed.returncode,
        "passed": len(nodes) if completed.returncode == 0 else None,
        "failed": 0 if completed.returncode == 0 else None,
        "skipped": 0 if completed.returncode == 0 else None,
        "elapsed_ns": ended_ns - started_ns,
        "raw_log_sha256": sha256(raw_path),
        "prepend_path": args.prepend_path or None,
        "retry_performed": False,
        "selected_v12_cases_executed": 0,
    }
    (output / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

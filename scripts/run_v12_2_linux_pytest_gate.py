from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--mode", choices=("serial", "default"), required=True)
    parser.add_argument("--text-output", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    nodes = manifest["nodes"]
    if len(nodes) != manifest["node_count"] or len({item["node_id"] for item in nodes}) != len(nodes):
        raise RuntimeError("invalid frozen Class-A node manifest")
    for item in nodes:
        source = ROOT / item["source_path"]
        if sha256(source) != item["source_sha256"]:
            raise RuntimeError(f"Class-A test source drift: {item['source_path']}")
    if args.text_output.exists() or args.json_output.exists():
        raise FileExistsError("refusing to overwrite V12.2 Linux gate evidence")

    command = ["python", "-m", "pytest", "-q"]
    if args.mode == "serial":
        command.extend(("-p", "no:xdist"))
    command.extend(item["node_id"] for item in nodes)
    started_ns = time.monotonic_ns()
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=os.environ.copy())
    ended_ns = time.monotonic_ns()
    text = completed.stdout + completed.stderr
    args.text_output.write_text(text, encoding="utf-8")
    summary = {
        "schema": "AgentTool.V12_2.LinuxPytestGate/1",
        "mode": args.mode,
        "manifest_sha256": sha256(manifest_path),
        "node_count": len(nodes),
        "exit_code": completed.returncode,
        "passed": len(nodes) if completed.returncode == 0 else None,
        "failed": 0 if completed.returncode == 0 else None,
        "skipped": 0 if completed.returncode == 0 else None,
        "elapsed_ns": ended_ns - started_ns,
        "command_uses_exact_frozen_node_list": True,
        "selected_v12_cases_executed": 0,
    }
    args.json_output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

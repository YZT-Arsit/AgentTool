from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PREREQUISITES = {
    "CANONICAL_SEMANTIC_HOLDOUT_V10_FREEZE.json": {
        "bytes": 45731,
        "sha256": "6699fe315ab35ab059c7e2e44e09f24a36ed07b047c1646d491f2daacaf10f9d",
    },
    "STRUCTURAL_SIZE_HOLDOUT_V10_FREEZE.json": {
        "bytes": 140996,
        "sha256": "2022c655161d339a2751637f997fa62a68c0bc600427d5d4adf9a17281a72827",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_v12_3_retained_v10_gate.py OUTPUT_ROOT")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)

    prerequisite_evidence = []
    for name, expected in EXPECTED_PREREQUISITES.items():
        path = ROOT / name
        observed = {"path": name, "bytes": path.stat().st_size, "sha256": sha256(path)}
        if observed["bytes"] != expected["bytes"] or observed["sha256"] != expected["sha256"]:
            raise RuntimeError(f"frozen prerequisite mismatch: {name}: {observed}")
        prerequisite_evidence.append(observed)

    serial = json.loads((ROOT / "V12_2_LINUX_SERIAL_GATE.json").read_text(encoding="utf-8"))
    nodes = [node for node in serial["failed_nodes"] if node.startswith("tests/test_v10_1_executor.py::")]
    if len(nodes) != 11 or len(set(nodes)) != 11:
        raise RuntimeError(f"expected exactly 11 unique retained V10.1 nodes, got {len(nodes)}")

    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:xdist", *nodes]
    started_ns = time.monotonic_ns()
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    ended_ns = time.monotonic_ns()
    raw = completed.stdout + completed.stderr
    raw_path = output / "pytest.txt"
    raw_path.write_text(raw, encoding="utf-8", newline="\n")
    result = {
        "schema": "AgentTool.V12_3.RetainedV10_1Gate/1",
        "nodes": nodes,
        "node_count": 11,
        "prerequisites": prerequisite_evidence,
        "exit_code": completed.returncode,
        "passed": 11 if completed.returncode == 0 else None,
        "failed": 0 if completed.returncode == 0 else None,
        "skipped": 0 if completed.returncode == 0 else None,
        "elapsed_ns": ended_ns - started_ns,
        "raw_log_sha256": sha256(raw_path),
        "native_and_canonical_execution_required_by_test_source": True,
        "retry_performed": False,
        "selected_v12_cases_executed": 0,
    }
    (output / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

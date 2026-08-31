from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_specs() -> list[str]:
    prior = json.loads((ROOT / "V12_CURRENT_NON_TIMING_PYTHON_MANIFEST.json").read_text(encoding="utf-8"))
    return [
        *prior["complete_files"],
        *prior["mixed_file_current_nodes"],
        "tests/test_v12_timing_pir_capacity.py",
        "tests/test_v12_microsoft_depth_contract.py",
        "tests/test_v12_timing_indistinguishability.py",
        "tests/test_v12_causal_horizon.py",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("serial", "default"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite Python gate output: {output}")
    output.mkdir(parents=True)
    specs = selected_specs()
    command = [sys.executable, "-m", "pytest", "-q", "--basetemp", str(output / "pytest_tmp")]
    if args.mode == "serial":
        command.extend(["-p", "no:xdist"])
    command.extend(specs)
    started = time.time_ns()
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log_path = output / "pytest.log"
    log_path.write_text(result.stdout, encoding="utf-8", newline="\n")
    record = {
        "schema": "AgentTool.V12CausalHorizonPostChangePythonGate/1",
        "phase": "V12-TIMING-CAUSAL-HORIZON-REQUALIFICATION",
        "mode": args.mode,
        "command": command,
        "source_specs": specs,
        "expected_node_count": 75,
        "started_ns": started,
        "ended_ns": time.time_ns(),
        "exit_code": result.returncode,
        "log_sha256": sha(log_path),
        "source_hashes": {
            path: sha(ROOT / path)
            for path in (
                "v12_timing/profile.py",
                "V12_CAUSAL_HORIZON_CAPACITY_MODEL.py",
                "tests/test_v12_causal_horizon.py",
                "tests/test_v12_timing_indistinguishability.py",
                "tests/test_v12_timing_pir_capacity.py",
                "tests/test_v12_microsoft_depth_contract.py",
            )
        },
        "selected_v12_cases_executed": 0,
        "timing_attack_sessions": 0,
    }
    (output / "gate.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

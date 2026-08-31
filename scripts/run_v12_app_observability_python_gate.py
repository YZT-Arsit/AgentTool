from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 100


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_specs() -> list[str]:
    prior = json.loads((ROOT / "V12_CURRENT_NON_TIMING_PYTHON_MANIFEST.json").read_text(encoding="utf-8"))
    return [*prior["complete_files"], *prior["mixed_file_current_nodes"],
            "tests/test_v12_timing_pir_capacity.py", "tests/test_v12_microsoft_depth_contract.py",
            "tests/test_v12_timing_indistinguishability.py", "tests/test_v12_causal_horizon.py",
            "tests/test_v12_timing_methodology_closure.py",
            "tests/test_v12_application_observability_delta.py"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("serial", "default"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite Python gate: {output}")
    output.mkdir(parents=True)
    command = [sys.executable, "-m", "pytest", "-q", "--basetemp", str(output / "pytest_tmp")]
    if args.mode == "serial":
        command.extend(["-p", "no:xdist"])
    command.extend(selected_specs())
    started = time.time_ns()
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = output / "pytest.log"
    log.write_text(result.stdout, encoding="utf-8", newline="\n")
    passed = result.returncode == 0 and f"{EXPECTED} passed" in result.stdout and " skipped" not in result.stdout
    record = {
        "schema": "AgentTool.V12ApplicationObservabilityPythonGate/1",
        "mode": args.mode, "command": command, "expected_tests": EXPECTED,
        "exit_code": result.returncode, "status": "PASS" if passed else "FAIL",
        "started_ns": started, "ended_ns": time.time_ns(), "log_sha256": sha(log),
        "classifier_training_runs": 0, "real_auc_calculations": 0,
    }
    (output / "gate.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

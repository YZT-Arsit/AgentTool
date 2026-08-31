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
    return [*prior["complete_files"], *prior["mixed_file_current_nodes"], "tests/test_v12_timing_pir_capacity.py"]


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
        "schema": "AgentTool.V12TPCICPostChangePythonGate/1",
        "mode": args.mode,
        "command": command,
        "source_specs": specs,
        "prior_manifest_sha256": sha(ROOT / "V12_CURRENT_NON_TIMING_PYTHON_MANIFEST.json"),
        "changed_source_hashes": {
            "v11_online/session.py": sha(ROOT / "v11_online/session.py"),
            "v12_timing/profile.py": sha(ROOT / "v12_timing/profile.py"),
            "v12_timing/capacity.py": sha(ROOT / "v12_timing/capacity.py"),
            "tests/test_v12_timing_pir_capacity.py": sha(ROOT / "tests/test_v12_timing_pir_capacity.py"),
        },
        "started_ns": started,
        "ended_ns": time.time_ns(),
        "exit_code": result.returncode,
        "log_sha256": sha(log_path),
        "selected_v12_cases_executed": 0,
    }
    (output / "gate.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

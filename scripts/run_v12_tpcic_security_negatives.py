from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite security-negative output: {output}")
    output.mkdir(parents=True)
    manifest_path = ROOT / "V12_NON_TIMING_SECURITY_NEGATIVE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    nodes = [item["test"] for item in manifest["cases"] if not item["test"].startswith("go:")]
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:xdist",
        "--basetemp",
        str(output / "pytest_tmp"),
        *nodes,
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = output / "python_negatives.log"
    log.write_text(result.stdout, encoding="utf-8", newline="\n")
    record = {
        "schema": "AgentTool.V12TPCICSecurityNegativeRerun/1",
        "manifest_sha256": sha(manifest_path),
        "python_case_count": len(nodes),
        "go_case_count": sum(item["test"].startswith("go:") for item in manifest["cases"]),
        "python_exit_code": result.returncode,
        "python_log_sha256": sha(log),
        "go_evidence": "/root/autodl-tmp/V12_TPCIC_GO_GATE.log contains all seven frozen Go negatives",
        "selected_v12_cases_executed": 0,
    }
    (output / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

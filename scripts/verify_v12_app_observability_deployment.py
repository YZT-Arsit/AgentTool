from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    file_rows = []
    for expected in manifest["files"]:
        path = ROOT / expected["path"]
        actual = sha(path) if path.is_file() else None
        file_rows.append({"path": expected["path"], "expected": expected["sha256"], "actual": actual,
                          "match": actual == expected["sha256"]})
    binary_rows = []
    for expected in manifest["binaries"]:
        path = ROOT / expected["path"]
        actual = sha(path) if path.is_file() else None
        binary_rows.append({"path": expected["path"], "expected": expected["sha256"], "actual": actual,
                            "match": actual == expected["sha256"]})
    probes = []
    for module_name, expected_relative in manifest["python_import_probes"].items():
        module = importlib.import_module(module_name)
        actual_path = Path(module.__file__).resolve()
        expected_path = (ROOT / expected_relative).resolve()
        probes.append({"module": module_name, "actual_path": str(actual_path), "expected_path": str(expected_path),
                       "path_match": actual_path == expected_path,
                       "hash_match": sha(actual_path) == sha(expected_path)})
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    passed = head == manifest["repository_commit"] and all(row["match"] for row in file_rows + binary_rows) and all(
        row["path_match"] and row["hash_match"] for row in probes)
    record = {
        "schema": "AgentTool.V12ApplicationObservabilityDeploymentVerification/1",
        "repository_commit_expected": manifest["repository_commit"], "repository_commit_actual": head,
        "file_matches": sum(row["match"] for row in file_rows), "file_total": len(file_rows),
        "binary_matches": sum(row["match"] for row in binary_rows), "binary_total": len(binary_rows),
        "module_probe_matches": sum(row["path_match"] and row["hash_match"] for row in probes),
        "module_probe_total": len(probes), "files": file_rows, "binaries": binary_rows,
        "module_probes": probes, "status": "PASS" if passed else "FAIL",
    }
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

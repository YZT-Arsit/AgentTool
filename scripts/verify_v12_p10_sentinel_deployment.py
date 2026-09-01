from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify exact P10 sentinel execution-host deployment.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite deployment verification: {args.output}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    file_rows = []
    for expected in manifest["files"]:
        path = ROOT / expected["path"]
        actual = sha256(path) if path.is_file() else None
        file_rows.append(
            {
                "path": expected["path"],
                "expected": expected["sha256"],
                "actual": actual,
                "match": actual == expected["sha256"],
            }
        )
    binary_rows = []
    for expected in manifest["binaries"]:
        path = ROOT / expected["path"]
        actual = sha256(path) if path.is_file() else None
        binary_rows.append(
            {
                "path": expected["path"],
                "expected": expected["sha256"],
                "actual": actual,
                "match": actual == expected["sha256"],
            }
        )
    probes = []
    for module_name, expected_relative in manifest["python_import_probes"].items():
        module = importlib.import_module(module_name)
        actual_path = Path(module.__file__).resolve()
        expected_path = (ROOT / expected_relative).resolve()
        probes.append(
            {
                "module": module_name,
                "actual_path": str(actual_path),
                "expected_path": str(expected_path),
                "path_match": actual_path == expected_path,
                "hash_match": sha256(actual_path) == sha256(expected_path),
            }
        )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    tracked_clean = (
        subprocess.run(["git", "diff", "--quiet"], cwd=ROOT, check=False).returncode == 0
        and subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False).returncode
        == 0
    )
    passed = (
        head == manifest["repository_commit"]
        and tracked_clean
        and sha256(args.freeze) == manifest["freeze_sha256"]
        and all(row["match"] for row in file_rows + binary_rows)
        and all(row["path_match"] and row["hash_match"] for row in probes)
    )
    record = {
        "schema": "AgentTool.V12P10TimingSentinelDeploymentVerification/1",
        "repository_commit_expected": manifest["repository_commit"],
        "repository_commit_actual": head,
        "tracked_source_clean": tracked_clean,
        "freeze_sha256_expected": manifest["freeze_sha256"],
        "freeze_sha256_actual": sha256(args.freeze),
        "file_matches": sum(row["match"] for row in file_rows),
        "file_total": len(file_rows),
        "binary_matches": sum(row["match"] for row in binary_rows),
        "binary_total": len(binary_rows),
        "module_probe_matches": sum(
            row["path_match"] and row["hash_match"] for row in probes
        ),
        "module_probe_total": len(probes),
        "files": file_rows,
        "binaries": binary_rows,
        "module_probes": probes,
        "protected_sentinel_sessions_before_verification": 0,
        "protected_auc_calculations_before_verification": 0,
        "status": "PASS" if passed else "FAIL",
    }
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

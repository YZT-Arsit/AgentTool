from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import site
import subprocess
import sys
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[dict[str, str]] = []
    actual_manifest_sha = sha(manifest_path)
    if args.expected_manifest_sha256 and actual_manifest_sha != args.expected_manifest_sha256:
        failures.append({"kind": "MANIFEST_SHA256", "expected": args.expected_manifest_sha256, "actual": actual_manifest_sha})

    checked: list[dict[str, object]] = []
    for item in manifest["files"]:
        path = root / item["path"]
        actual = sha(path) if path.is_file() else "MISSING"
        passed = actual == item["sha256"]
        checked.append({"path": item["path"], "expected": item["sha256"], "actual": actual, "passed": passed})
        if not passed:
            failures.append({"kind": "FILE_SHA256", "path": item["path"], "expected": item["sha256"], "actual": actual})

    binaries: list[dict[str, object]] = []
    for item in manifest["binaries"]:
        path = root / item["path"]
        actual = sha(path) if path.is_file() else "MISSING"
        passed = actual == item["sha256"]
        binaries.append({**item, "resolved_path": str(path), "actual_sha256": actual, "passed": passed})
        if not passed:
            failures.append({"kind": "BINARY_SHA256", "path": item["path"], "expected": item["sha256"], "actual": actual})

    # Match the timing driver's repository-root import contract exactly.
    sys.path.insert(0, str(root))
    probes: list[dict[str, object]] = []
    for module_name, expected_relative in manifest["python_import_probes"].items():
        expected_path = (root / expected_relative).resolve()
        try:
            module = importlib.import_module(module_name)
            actual_path = Path(module.__file__).resolve()
            actual_hash = sha(actual_path)
            expected_hash = sha(expected_path)
            passed = actual_path == expected_path and actual_hash == expected_hash
            probes.append(
                {
                    "module": module_name,
                    "actual_file": str(actual_path),
                    "expected_file": str(expected_path),
                    "actual_sha256": actual_hash,
                    "expected_sha256": expected_hash,
                    "passed": passed,
                }
            )
            if not passed:
                failures.append({"kind": "PYTHON_MODULE_FILE", "module": module_name, "expected": str(expected_path), "actual": str(actual_path)})
        except BaseException as exc:
            probes.append({"module": module_name, "passed": False, "error": f"{type(exc).__name__}: {exc}"})
            failures.append({"kind": "PYTHON_IMPORT", "module": module_name, "actual": f"{type(exc).__name__}: {exc}"})

    pth_bindings: list[dict[str, str]] = []
    for directory in site.getsitepackages():
        for path in sorted(Path(directory).glob("*.pth")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(token in text for token in ("mediation_trace_validation", "openai-agents-python", "agent-framework")):
                pth_bindings.append({"path": str(path.resolve()), "sha256": sha(path), "content": text.strip()})

    git_identity: dict[str, object]
    if (root / ".git").exists():
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, capture_output=True, text=True).stdout
        git_identity = {"available": True, "head": head, "clean": status == "", "status": status}
        if head != manifest["base_commit"] and not all(bool(item["passed"]) for item in checked):
            failures.append({"kind": "DEPLOYED_SOURCE_IDENTITY", "expected": manifest["base_commit"], "actual": head})
    else:
        git_identity = {"available": False, "deployed_source_identity": "TRANSITIVE_ARTIFACT_MANIFEST"}

    output = {
        "schema": "AgentTool.V12TimingDeploymentVerification/1",
        "manifest_sha256": actual_manifest_sha,
        "root": str(root),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": sys.version,
        "git_or_deployed_source_identity": git_identity,
        "file_hash_match": f"{sum(bool(item['passed']) for item in checked)}/{len(checked)}",
        "binary_hash_match": f"{sum(bool(item['passed']) for item in binaries)}/{len(binaries)}",
        "python_module_file_match": f"{sum(bool(item['passed']) for item in probes)}/{len(probes)}",
        "files": checked,
        "binaries": binaries,
        "python_module_file_probes": probes,
        "pth_source_bindings": pth_bindings,
        "failures": failures,
        "deployment_integrity": "PASS" if not failures else "FAIL",
        "development_identities_authorized": not failures,
    }
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite deployment verification: {args.output}")
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

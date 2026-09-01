from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from v12_timing.microsoft_t7_rca import build_freeze_manifest

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_PATHS = (
    "v12_timing/microsoft_t7_rca.py",
    "v11_online/frameworks.py",
    "v11_full_scope/frameworks.py",
    "v12_timing/isolated_tasks.py",
    "scripts/freeze_v12_microsoft_t7_rca.py",
    "scripts/run_v12_microsoft_t7_rca.py",
)
FRAMEWORK_PATHS = (
    "external_stage9/agent-framework/python/packages/core/agent_framework/_agents.py",
    "external_stage9/agent-framework/python/packages/core/agent_framework/_tools.py",
    "external_stage9/agent-framework/python/packages/core/agent_framework/_clients.py",
)


def git_blob_sha256(relative: str, *, revision: str = "HEAD") -> str:
    blob = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(blob).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze Microsoft T7 semantic RCA matrix.")
    parser.add_argument("--deployment-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite RCA freeze: {args.output}")
    if subprocess.run(["git", "diff", "--quiet"], cwd=ROOT, check=False).returncode:
        raise SystemExit("tracked RCA source has unstaged changes")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False).returncode:
        raise SystemExit("tracked RCA source has staged changes")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    deployment = json.loads(args.deployment_manifest.read_text(encoding="utf-8"))
    file_hashes = {row["path"]: row["sha256"] for row in deployment["files"]}
    missing = set(FRAMEWORK_PATHS) - file_hashes.keys()
    if missing:
        raise SystemExit(f"deployment manifest lacks pinned framework source: {sorted(missing)}")
    framework_commit = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT / ".." / "mediation_trace_validation" / "external_stage9" / "agent-framework"),
            "rev-parse",
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = build_freeze_manifest(
        execution_source_commit=head,
        framework_commit=framework_commit,
        framework_source_hashes={path: file_hashes[path] for path in FRAMEWORK_PATHS},
        analysis_hashes={path: git_blob_sha256(path, revision=head) for path in ANALYSIS_PATHS},
    )
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "payload_sha256": manifest["payload_sha256"],
                "diagnostic_identities": manifest["diagnostic_identity_count"],
                "repetitions_per_coordinate": manifest["repetitions_per_coordinate"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

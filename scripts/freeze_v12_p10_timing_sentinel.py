from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.sentinel import PROTOCOL_BASE_SHA, build_freeze_manifest

HASHED_ANALYSIS_PATHS = (
    "v12_timing/classifier.py",
    "v12_timing/projection.py",
    "v12_timing/statistics.py",
    "v12_timing/sentinel.py",
    "scripts/collect_v12_p10_timing_sentinel.py",
    "scripts/analyze_v12_p10_timing_sentinel.py",
)


def git_blob_sha256(relative: str, *, revision: str = "HEAD") -> str:
    """Hash committed bytes so the freeze is independent of checkout EOL policy."""

    blob = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(blob).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze P10 sentinel identities and schedule.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite sentinel freeze: {args.output}")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if status:
        raise SystemExit("sentinel freeze requires a clean committed execution-source tree")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    lineage = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PROTOCOL_BASE_SHA, head], cwd=ROOT, check=False
    ).returncode
    if lineage:
        raise SystemExit("execution source does not descend from the immutable protocol baseline")
    hashes = {relative: git_blob_sha256(relative, revision=head) for relative in HASHED_ANALYSIS_PATHS}
    manifest = build_freeze_manifest(execution_source_commit=head, analysis_hashes=hashes)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "payload_sha256": manifest["payload_sha256"],
                "identities": manifest["total_physical_sessions"],
                "pairs": len(manifest["pairs"]),
                "physical_coordinates": manifest["physical_coordinate_count"],
                "observer_comparisons": manifest["observer_comparison_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

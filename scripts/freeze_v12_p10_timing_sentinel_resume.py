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

from v12_timing.sentinel_resume import (
    LATEST_DEVELOPMENT_EVIDENCE_SHA,
    PROTOCOL_BASE_SHA,
    build_freeze_manifest,
)

HASHED_ANALYSIS_PATHS = (
    "v12_timing/classifier.py",
    "v12_timing/projection.py",
    "v12_timing/statistics.py",
    "v12_timing/sentinel.py",
    "v12_timing/sentinel_resume.py",
    "scripts/collect_v12_p10_timing_sentinel_resume.py",
    "scripts/analyze_v12_p10_timing_sentinel_resume.py",
)

EXCLUSION_FILES = (
    "V12_P10_TIMING_SENTINEL_FREEZE.json",
    "V12_APPLICATION_OBSERVABILITY_DEVELOPMENT_EXCLUSIONS.json",
    "V12_TIMING_DEVELOPMENT_EXCLUSIONS.json",
    "V12_TIMING_DEVELOPMENT_EXCLUSIONS_V2.json",
)

IDENTITY_KEYS = (
    "identities",
    "excluded_observed_identities",
    "prior_functional_identities",
    "prior_methodology_identities",
    "current_methodology_test_identities",
    "local_synthetic_control_identities",
)


def git_blob_sha256(relative: str, *, revision: str) -> str:
    blob = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(blob).hexdigest()


def _exclusions() -> tuple[list[str], dict[str, str]]:
    identities: set[str] = set()
    sources: dict[str, str] = {}
    for relative in EXCLUSION_FILES:
        path = ROOT / relative
        if not path.is_file():
            continue
        sources[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if relative == "V12_P10_TIMING_SENTINEL_FREEZE.json":
            identities.update(str(value) for value in payload["identity_manifest"])
        for key in IDENTITY_KEYS:
            identities.update(str(value) for value in payload.get(key, []))
    return sorted(identities), sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze fresh P10 resume sentinel identities.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite resume sentinel freeze: {args.output}")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if status:
        raise SystemExit("resume sentinel freeze requires a clean committed execution-source tree")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head == LATEST_DEVELOPMENT_EVIDENCE_SHA:
        raise SystemExit("resume sentinel harness must be committed before identities are frozen")
    for ancestor in (LATEST_DEVELOPMENT_EVIDENCE_SHA, PROTOCOL_BASE_SHA):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, head], cwd=ROOT, check=False
        ).returncode:
            raise SystemExit(f"execution source does not descend from required baseline {ancestor}")
    hashes = {
        relative: git_blob_sha256(relative, revision=head)
        for relative in HASHED_ANALYSIS_PATHS
    }
    excluded, sources = _exclusions()
    manifest = build_freeze_manifest(
        execution_source_commit=head,
        analysis_hashes=hashes,
        excluded_identities=excluded,
        exclusion_sources=sources,
    )
    args.output.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "payload_sha256": manifest["payload_sha256"],
                "identities": manifest["total_physical_sessions"],
                "pairs": len(manifest["pairs"]),
                "planned_train_blocks": manifest["planned_train_blocks_per_coordinate"],
                "planned_eval_blocks": manifest["planned_eval_blocks_per_coordinate"],
                "excluded_identities": len(excluded),
                "new_identity_overlap": 0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

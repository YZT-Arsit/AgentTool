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

from v12_timing.sentinel_duplex import build_freeze_manifest

HASHED_PATHS = (
    "v12_timing/classifier.py",
    "v12_timing/projection.py",
    "v12_timing/statistics.py",
    "v12_timing/sentinel.py",
    "v12_timing/sentinel_resume.py",
    "v12_timing/sentinel_duplex.py",
    "scripts/collect_v12_p10_timing_sentinel_resume.py",
    "scripts/collect_v12_duplex_p10_sentinel.py",
    "scripts/analyze_v12_p10_timing_sentinel_resume.py",
    "scripts/analyze_v12_duplex_p10_sentinel.py",
    "scripts/freeze_v12_duplex_p10_analysis.py",
    "scripts/freeze_v12_duplex_p10_sentinel.py",
    "scripts/build_v12_duplex_p10_sentinel_deployment_manifest.py",
    "scripts/verify_v12_duplex_p10_sentinel_deployment.py",
)
EXCLUSION_FILES = (
    "V12_P10_TIMING_SENTINEL_FREEZE.json",
    "V12_P10_TIMING_SENTINEL_RESUME_FREEZE.json",
    "V12_P10_TIMING_SENTINEL_V3_FREEZE.json",
    "V12_DUPLEX_FUNCTIONAL_FREEZE_V7.json",
    "V12_DUPLEX_DEVELOPMENT_EXCLUSIONS.json",
    "V12_APPLICATION_OBSERVABILITY_DEVELOPMENT_EXCLUSIONS.json",
    "V12_TIMING_DEVELOPMENT_EXCLUSIONS.json",
    "V12_TIMING_DEVELOPMENT_EXCLUSIONS_V2.json",
    "V12_CAUSAL_HORIZON_DEVELOPMENT_EXCLUSIONS.json",
)


def git_blob_sha256(relative: str, revision: str) -> str:
    data = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(data).hexdigest()


def exclusions() -> tuple[list[str], dict[str, str]]:
    identities: set[str] = set()
    sources: dict[str, str] = {}
    for relative in EXCLUSION_FILES:
        path = ROOT / relative
        if not path.is_file():
            continue
        sources[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        value = json.loads(path.read_text(encoding="utf-8"))
        manifest = value.get("identity_manifest", {})
        if isinstance(manifest, dict):
            identities.update(str(identity) for identity in manifest)
        for key in (
            "identities",
            "excluded_observed_identities",
            "prior_functional_identities",
            "prior_methodology_identities",
            "current_methodology_test_identities",
            "local_synthetic_control_identities",
        ):
            rows = value.get(key, [])
            if isinstance(rows, list):
                identities.update(str(row) for row in rows if isinstance(row, str))
        if relative == "V12_DUPLEX_FUNCTIONAL_FREEZE_V7.json":
            for profile in value["profiles"]:
                for framework in value["frameworks"]:
                    framework_code = "OA" if framework == "OpenAI Agents SDK" else "MS"
                    for workload in value["workloads"]:
                        identities.add(
                            f"DEV-DTVR-V4R5-P{profile['delta_ms']}-{framework_code}-{workload}-{value['identity_suffix']}"
                        )
    return sorted(identities), sources


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite sentinel freeze: {args.output}")
    if subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise SystemExit("sentinel freeze requires a clean committed source tree")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            "bf499d5e56507eb069d4998a2851cfaa23ec7fc6",
            head,
        ],
        cwd=ROOT,
        check=False,
    ).returncode:
        raise SystemExit("execution source does not descend from duplex evidence")
    excluded, sources = exclusions()
    manifest = build_freeze_manifest(
        execution_source_commit=head,
        analysis_hashes={path: git_blob_sha256(path, head) for path in HASHED_PATHS},
        excluded_identities=excluded,
        exclusion_sources=sources,
    )
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "identities": len(manifest["identity_manifest"]),
                "excluded": len(excluded),
                "payload_sha256": manifest["payload_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

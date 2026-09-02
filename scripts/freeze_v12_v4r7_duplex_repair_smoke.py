from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.sentinel_smoke_v4r7 import build_freeze_manifest

HASHED_PATHS = (
    "v12_timing/classifier.py",
    "v12_timing/projection.py",
    "v12_timing/statistics.py",
    "v12_timing/sentinel_resume.py",
    "v12_timing/sentinel_smoke.py",
    "v12_timing/sentinel_smoke_v4r7.py",
    "scripts/collect_v12_p10_timing_sentinel_resume.py",
    "scripts/collect_v12_v4r7_duplex_repair_smoke.py",
    "scripts/analyze_v12_p10_timing_sentinel_resume.py",
    "scripts/analyze_v12_duplex_repair_smoke.py",
    "scripts/analyze_v12_v4r7_duplex_repair_smoke.py",
    "scripts/freeze_v12_duplex_repair_smoke_analysis.py",
    "scripts/freeze_v12_v4r7_duplex_repair_smoke_analysis.py",
    "scripts/freeze_v12_v4r7_duplex_repair_smoke.py",
)
IDENTITY = re.compile(r"DEV-[A-Za-z0-9_-]+")


def sha256_blob(relative: str, revision: str) -> str:
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
    for path in sorted(ROOT.glob("V12*.json")):
        text = path.read_text(encoding="utf-8", errors="replace")
        found = set(IDENTITY.findall(text))
        if found:
            identities.update(found)
            sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    for directory in sorted(ROOT.glob("V12*EVIDENCE")):
        for path in sorted(directory.rglob("*.json")):
            text = path.read_text(encoding="utf-8", errors="replace")
            found = set(IDENTITY.findall(text))
            if found:
                identities.update(found)
                relative = path.relative_to(ROOT).as_posix()
                sources[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return sorted(identities), sources


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite V4R7 smoke freeze: {args.output}")
    for command, message in (
        (["git", "diff", "--quiet"], "clean tracked source"),
        (["git", "diff", "--cached", "--quiet"], "clean index"),
    ):
        if subprocess.run(command, cwd=ROOT, check=False).returncode:
            raise SystemExit(f"V4R7 smoke freeze requires {message}")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    excluded, sources = exclusions()
    manifest = build_freeze_manifest(
        execution_source_commit=head,
        analysis_hashes={path: sha256_blob(path, head) for path in HASHED_PATHS},
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
                "new_identity_overlap": 0,
                "payload_sha256": manifest["payload_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

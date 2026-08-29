"""Create the immutable, content-addressed V6 research freeze manifest.

The manifest deliberately records every regular file in the V6 implementation,
its canonical reports/tables, and results_v6.  Transient IPC files, interpreter
caches, and locally built executables are not research artifacts and are listed
as exclusions in the manifest instead of being hashed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "V6_FREEZE_MANIFEST.json"

SOURCE_ROOTS = (
    "action_privacy_v6",
    "common_action_gateway_v2",
)
SOURCE_FILES = (
    "gateway_v2/runner.py",
    "cryptographic_closure/pir_backend.py",
)
REPORT_GLOBS = (
    "*V6*.md",
    "*V6*.csv",
    "*V6*.json",
    "*V6*.txt",
)

EXCLUDED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".shared",
    "bin",
}
EXCLUDED_SUFFIXES = {".exe", ".pyc", ".pyo", ".test"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def include_file(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        path.is_file()
        and not any(part in EXCLUDED_PARTS for part in relative.parts)
        and path.suffix.lower() not in EXCLUDED_SUFFIXES
        and path != OUTPUT
    )


def collect() -> tuple[list[Path], list[dict[str, str]]]:
    candidates: set[Path] = set()
    exclusions: list[dict[str, str]] = []

    for relative_root in SOURCE_ROOTS:
        root = ROOT / relative_root
        if root.exists():
            for path in root.rglob("*"):
                if include_file(path):
                    candidates.add(path)
                elif path.is_file():
                    exclusions.append(
                        {
                            "path": path.relative_to(ROOT).as_posix(),
                            "reason": "transient cache, IPC state, or local build product",
                        }
                    )

    for relative_file in SOURCE_FILES:
        path = ROOT / relative_file
        if include_file(path):
            candidates.add(path)

    for pattern in REPORT_GLOBS:
        for path in ROOT.glob(pattern):
            if include_file(path):
                candidates.add(path)

    results_root = ROOT / "results_v6"
    if results_root.exists():
        for path in results_root.rglob("*"):
            if include_file(path):
                candidates.add(path)
            elif path.is_file():
                exclusions.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "reason": "transient cache, IPC state, or local build product",
                    }
                )

    return sorted(candidates), sorted(exclusions, key=lambda row: row["path"])


def git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite immutable manifest: {OUTPUT}")

    files, exclusions = collect()
    entries = []
    for path in files:
        stat = path.stat()
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": stat.st_size,
                "sha256": sha256(path),
            }
        )

    manifest = {
        "schema": "agenttool-v6-freeze-manifest-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "repository_git_head": git_head(),
        "freeze_policy": (
            "Canonical V6 implementation, reports, tables, and results are immutable. "
            "V7 changes must use new files or explicitly versioned V7 paths."
        ),
        "entry_count": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "entries": entries,
        "excluded_transient_files": exclusions,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} with {len(entries)} entries")


if __name__ == "__main__":
    main()

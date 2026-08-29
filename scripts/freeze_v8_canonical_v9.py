from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "V8_CANONICAL_FREEZE_V9.json"
EXPECTED_HEAD = "335ccbcb415de9a79fa2b53be2b50d51bfdad2ee"


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_v8_evidence(relative: Path) -> bool:
    posix = relative.as_posix()
    name = relative.name.upper()
    return (
        posix.startswith("action_privacy_v8/")
        or posix.startswith("common_action_gateway_v2/v8/")
        or posix.startswith("results_v8/")
        or (posix.startswith("scripts/") and "V8" in name)
        or (posix.startswith("tests/") and "V8" in name)
        or (len(relative.parts) == 1 and "V8" in name)
        or name in {"V6_FREEZE_MANIFEST.JSON", "V7_PRE_OHTTP_FREEZE_MANIFEST.JSON"}
    )


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite frozen manifest: {OUTPUT}")
    head = git("rev-parse", "HEAD")
    if head != EXPECTED_HEAD:
        raise SystemExit(f"unexpected V8 baseline: {head}")
    status_lines = [line for line in git("status", "--porcelain").splitlines() if line]
    allowed_new = {"?? scripts/freeze_v8_canonical_v9.py"}
    unexpected = [line for line in status_lines if line not in allowed_new]
    if unexpected:
        raise SystemExit(f"V8 freeze found unexpected worktree state: {unexpected}")

    tracked = [Path(line) for line in git("ls-files").splitlines() if line]
    selected = sorted((path for path in tracked if is_v8_evidence(path)), key=lambda p: p.as_posix())
    entries = []
    for relative in selected:
        path = ROOT / relative
        entries.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )

    payload = {
        "schema": "AgentTool.V8CanonicalFreezeV9/1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "repository_head": head,
        "repository_tree": git("rev-parse", "HEAD^{tree}"),
        "worktree_clean_at_freeze": True,
        "scope": "Tracked V8 implementation/evidence plus predecessor freeze manifests. The repository commit/tree freezes all V1-V8 tracked state.",
        "entry_count": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "entries": entries,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("repository_head", "repository_tree", "entry_count", "total_bytes")}))


if __name__ == "__main__":
    main()

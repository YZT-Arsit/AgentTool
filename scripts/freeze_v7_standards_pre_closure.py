from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "V7_STANDARDS_PRE_CLOSURE_FREEZE.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidates() -> list[Path]:
    selected: set[Path] = set()
    for directory in (
        "action_privacy_v7_ohttp",
        "common_action_gateway_v2/v7",
        "common_action_gateway_v2/v7ohttp",
        "gateway_v7",
        "results_v7",
        "results_v7_ohttp",
    ):
        path = ROOT / directory
        if path.exists():
            selected.update(item for item in path.rglob("*") if item.is_file())
    selected.update(
        path
        for path in (ROOT / "tests").glob("*v7*.*")
        if path.is_file()
    )
    for path in ROOT.iterdir():
        if not path.is_file() or path == OUTPUT:
            continue
        name = path.name.upper()
        if "V7" in name and path.suffix.lower() in {".md", ".csv", ".json", ".txt"}:
            selected.add(path)
    for name in ("V6_FREEZE_MANIFEST.json", "V7_PRE_OHTTP_FREEZE_MANIFEST.json"):
        path = ROOT / name
        if path.exists():
            selected.add(path)
    return sorted(selected, key=lambda path: path.relative_to(ROOT).as_posix())


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite frozen manifest: {OUTPUT}")
    paths = candidates()
    entries = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in paths
    ]
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        head = "UNAVAILABLE"
    payload = {
        "schema": "AgentTool.V7StandardsPreClosureFreeze/1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "user_identified_v7_baseline": "faa905a4cf5403f762daf0194f1ad98e42a3c092",
        "repository_head_at_freeze": head,
        "policy": "Immutable V1-V7 evidence. All subsequent implementation and results are V8 closure artifacts.",
        "entry_count": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "entries": entries,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("entry_count", "total_bytes", "repository_head_at_freeze")}))


if __name__ == "__main__":
    main()

"""Freeze the completed pre-OHTTP V7 closure evidence before refactoring."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "V7_PRE_OHTTP_FREEZE_MANIFEST.json"
ROOTS = (
    "common_action_gateway_v2/v7",
    "common_action_gateway_v2/cmd/gateway-pacer-v7",
    "common_action_gateway_v2/cmd/gateway-worker-v7",
    "gateway_v7",
    "results_v7",
)
FILES = (
    "GATEWAY_RESULT_DELIVERY_ROOT_CAUSE_V7.md",
    "GATEWAY_OPERATION_LIFECYCLE_V7.csv",
    "ACTION_MEDIATION_PARTIAL_PARETO_V7.csv",
    "ACTION_MEDIATION_PARTIAL_PARETO_V7.md",
    "ACTION_MEDIATION_COVERAGE_V7.csv",
    "ACTION_MEDIATION_COVERAGE_V7.md",
    "ACTION_SEMANTIC_HOLDOUT_V7_FREEZE.json",
    "ACTION_SEMANTIC_HOLDOUT_V7_FREEZE_SHA256.txt",
    "ACTION_SEMANTIC_HOLDOUT_V7.csv",
    "STRICT_DEVELOPMENT_RESULTS_V7.csv",
    "STRUCTURAL_SIZE_HOLDOUT_V7_FREEZE.json",
    "STRUCTURAL_SIZE_HOLDOUT_V7_FREEZE_SHA256.txt",
    "STRUCTURAL_SIZE_HOLDOUT_V7.csv",
    "LONG_HORIZON_V7.csv",
    "BASELINE_MATRIX_V7.md",
    "EXPERIMENT_MATRIX_V7.md",
    "EXPERIMENT_MATRIX_V7.csv",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite freeze: {OUTPUT}")
    paths: set[Path] = set()
    for relative in ROOTS:
        root = ROOT / relative
        if root.exists():
            paths.update(path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    for relative in FILES:
        path = ROOT / relative
        if path.exists():
            paths.add(path)
    entries = [
        {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(paths)
    ]
    manifest = {
        "schema": "agenttool-v7-pre-ohttp-freeze-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "IMMUTABLE_PRE_OHTTP_ENGINEERING_EVIDENCE",
        "interpretation": (
            "Reliability, semantics, and legacy custom-wire structural evidence only. "
            "It is not RFC 9458 OHTTP evidence and cannot be cited as such."
        ),
        "entries": entries,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"froze {len(entries)} files")


if __name__ == "__main__":
    main()

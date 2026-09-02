from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.sentinel_smoke_v4r7_late_frame import validate_freeze_manifest

COLLECTION_SOURCE_COMMIT = "7bf3ef70295c39e19c45b95fbde61055ca3d6d5a"
ORIGINAL_SENTINEL_SMOKE_SHA256 = (
    "590b879f258c96e90333170cfbf65ebf2afc740130b666d253193de8d4cde2e51"
)
BOUND_SENTINEL_SMOKE_SHA256 = (
    "f2d58decae497c4cae4de757234b7e110114396e26642a20936096e4d98aaf1e"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload_sha256(value: dict[str, Any]) -> str:
    payload = dict(value)
    payload.pop("payload_sha256", None)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_analysis_authority(
    collection_freeze: dict[str, Any], *, analysis_source_commit: str
) -> dict[str, Any]:
    if collection_freeze["execution_source_commit"] != COLLECTION_SOURCE_COMMIT:
        raise ValueError("unexpected collection execution source")
    hashes = collection_freeze["analysis_hashes"]
    if hashes["v12_timing/sentinel_smoke.py"] != ORIGINAL_SENTINEL_SMOKE_SHA256:
        raise ValueError("unexpected original smoke-denominator binding hash")
    authority = copy.deepcopy(collection_freeze)
    authority["execution_source_commit"] = analysis_source_commit
    authority["analysis_hashes"]["v12_timing/sentinel_smoke.py"] = (
        BOUND_SENTINEL_SMOKE_SHA256
    )
    authority["payload_sha256"] = payload_sha256(authority)
    return authority


def write_new(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite analysis-binding evidence: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if sha256(ROOT / "v12_timing/sentinel_smoke.py") != BOUND_SENTINEL_SMOKE_SHA256:
        raise RuntimeError("smoke-denominator binding source hash drifted")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    collection = json.loads(args.collection_manifest.read_text(encoding="utf-8"))
    validate_freeze_manifest(collection)
    authority = build_analysis_authority(collection, analysis_source_commit=head)
    validate_freeze_manifest(authority)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    authority_path = args.output_dir / "analysis_authority_manifest.json"
    closure_path = args.output_dir / "analysis_binding_closure.json"
    write_new(authority_path, authority)
    closure = {
        "schema": "AgentTool.V12V4R7SmokeAnalysisBindingClosure/1",
        "status": "PASS",
        "failure_stage": "PRE_MODEL_FIT_COMPLETE_BLOCK_SELECTION",
        "completed_classifier_fits_before_repair": 0,
        "protected_auc_calculations_before_repair": 0,
        "collection_manifest_sha256": sha256(args.collection_manifest),
        "collection_source_commit": COLLECTION_SOURCE_COMMIT,
        "analysis_source_commit": head,
        "changed_source": "v12_timing/sentinel_smoke.py",
        "original_source_sha256": ORIGINAL_SENTINEL_SMOKE_SHA256,
        "bound_source_sha256": BOUND_SENTINEL_SMOKE_SHA256,
        "repair": "BIND_SHARED_COMPLETION_SELECTION_TO_FROZEN_64_30_30",
        "observer_feature_diff": "NONE",
        "statistical_protocol_diff": "NONE",
        "dataset_diff": "NONE",
        "block_priority_diff": "NONE",
    }
    write_new(closure_path, closure)
    print(
        json.dumps(
            {
                "analysis_authority_manifest_sha256": sha256(authority_path),
                "analysis_binding_closure_sha256": sha256(closure_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

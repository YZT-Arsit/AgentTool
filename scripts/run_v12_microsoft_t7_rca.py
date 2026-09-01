from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from v12_timing.microsoft_t7_rca import (
    FAILED_IMMUTABLE_IDENTITY,
    diagnostic_schedule,
    run_diagnostic,
    validate_freeze_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def verify_execution_source(manifest: dict[str, Any]) -> dict[str, Any]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != manifest["execution_source_commit"]:
        raise RuntimeError("RCA runner commit differs from frozen source")
    for relative, expected in manifest["analysis_hashes"].items():
        blob = subprocess.run(
            ["git", "show", f"HEAD:{relative}"], cwd=ROOT, check=True, capture_output=True
        ).stdout
        if hashlib.sha256(blob).hexdigest() != expected:
            raise RuntimeError(f"RCA analysis source mismatch: {relative}")
    framework_root = ROOT / "external_stage9" / "agent-framework"
    framework_commit = subprocess.run(
        ["git", "-C", str(framework_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if framework_commit != manifest["framework_commit"]:
        raise RuntimeError("pinned Microsoft framework commit mismatch")
    source_matches: dict[str, bool] = {}
    for relative, expected in manifest["framework_source_hashes"].items():
        path = ROOT / relative
        source_matches[relative] = path.is_file() and sha256(path) == expected
    if not all(source_matches.values()):
        raise RuntimeError("pinned Microsoft framework source hash mismatch")
    module = importlib.import_module("agent_framework")
    imported = Path(module.__file__).resolve()
    expected_import = (
        ROOT
        / "external_stage9/agent-framework/python/packages/core/agent_framework/__init__.py"
    ).resolve()
    if imported != expected_import:
        raise RuntimeError("RCA imported a different Microsoft framework")
    return {
        "repository_commit": head,
        "framework_commit": framework_commit,
        "framework_source_matches": source_matches,
        "framework_import_path": str(imported),
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen semantic-only Microsoft T7 RCA.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite or resume RCA evidence: {args.output}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_freeze_manifest(manifest)
    deployment = verify_execution_source(manifest)
    args.output.mkdir(parents=True)
    (args.output / "frozen_manifest.json").write_bytes(args.manifest.read_bytes())
    write_json(args.output / "deployment_verification.json", deployment)
    state: dict[str, Any] = {
        "schema": "AgentTool.V12MicrosoftT7SemanticRCAState/1",
        "status": "RUNNING",
        "expected_identities": 1200,
        "completed_identities": 0,
        "diagnostic_retries": 0,
        "failed_immutable_identity_reexecuted": False,
        "timing_features_collected": False,
        "classifier_training": 0,
        "auc_calculations": 0,
    }
    write_json(args.output / "state.json", state)
    ledger_path = args.output / "semantic_results.jsonl"
    previous_hash = "0" * 64
    inventory: list[dict[str, Any]] = []
    for ordinal, spec in enumerate(diagnostic_schedule()):
        if spec.identity == FAILED_IMMUTABLE_IDENTITY:
            raise AssertionError("failed sentinel identity entered RCA execution")
        result = run_diagnostic(spec)
        row = {
            "execution_ordinal": ordinal,
            "previous_record_sha256": previous_hash,
            **result,
        }
        encoded = json.dumps(row, sort_keys=True, separators=(",", ":"))
        with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")
        previous_hash = hashlib.sha256(encoded.encode()).hexdigest()
        inventory.append(
            {
                "identity": spec.identity,
                "coordinate": spec.coordinate,
                "classification": result["classification"],
                "record_sha256": previous_hash,
            }
        )
        state["completed_identities"] = ordinal + 1
        state["last_record_sha256"] = previous_hash
        write_json(args.output / "state.json", state)
    counts: dict[str, dict[str, int]] = {}
    for coordinate in manifest["coordinates"]:
        counts[coordinate] = dict(
            sorted(
                Counter(
                    row["classification"]
                    for row in inventory
                    if row["coordinate"] == coordinate
                ).items()
            )
        )
    summary: dict[str, Any] = {
        "schema": "AgentTool.V12MicrosoftT7SemanticRCASummary/1",
        "status": "COMPLETE",
        "manifest_sha256": sha256(args.manifest),
        "diagnostic_identities": len(inventory),
        "diagnostic_retries": 0,
        "failed_immutable_identity_reexecuted": False,
        "semantic_counts": counts,
        "semantic_results_sha256": sha256(ledger_path),
        "semantic_inventory_sha256": canonical_sha256(inventory),
        "last_record_sha256": previous_hash,
        "timing_features_collected": False,
        "classifier_training": 0,
        "auc_calculations": 0,
    }
    write_json(args.output / "summary.json", summary)
    state.update(
        {
            "status": "COMPLETE",
            "completed_identities": 1200,
            "summary_sha256": sha256(args.output / "summary.json"),
        }
    )
    write_json(args.output / "state.json", state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

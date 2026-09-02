from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def write_new(path: Path, value: object) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite abort evidence: {path}")
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    args = parser.parse_args()
    root = args.campaign
    freeze_path = root / "frozen_manifest.json"
    state_path = root / "collection_state.json"
    ledger_path = root / "execution_ledger.jsonl"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state["status"] != "COLLECTION_OPEN" or int(state["retries"]) != 0:
        raise RuntimeError("cost abort closure requires the interrupted open campaign")
    ledger = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    if len(ledger) != int(state["executed_sessions"]):
        raise RuntimeError("finalized ledger count differs from collection state")
    previous = "0" * 64
    records = []
    for index, row in enumerate(ledger):
        if (
            int(row["execution_ordinal"]) != index
            or row["previous_ledger_record_sha256"] != previous
        ):
            raise RuntimeError("execution ledger chain is malformed")
        encoded = json.dumps(row, sort_keys=True, separators=(",", ":"))
        previous = hashlib.sha256(encoded.encode()).hexdigest()
        path = root / row["record_path"]
        if sha256(path) != row["record_sha256"]:
            raise RuntimeError("preserved session record hash mismatch")
        records.append(
            {
                "identity": row["identity"],
                "status": row["status"],
                "path": row["record_path"],
                "sha256": row["record_sha256"],
            }
        )
    session_root = root / "sessions"
    directories = sorted(path for path in session_root.iterdir() if path.is_dir())
    finalized_roots = {str(Path(row["record_path"]).parent) for row in ledger}
    partial = [
        path
        for path in directories
        if path.relative_to(root).as_posix() not in finalized_roots
    ]
    if len(partial) != 1 or len(directories) != len(ledger) + 1:
        raise RuntimeError("expected exactly one interrupted in-flight identity")
    partial_root = partial[0]
    partial_files = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(partial_root.rglob("*"))
        if path.is_file()
    ]
    interrupted_ordinal = int(partial_root.name.split("_", 1)[0])
    expected = freeze["execution_schedule"][interrupted_ordinal]
    if expected["identity"] not in partial_root.name:
        raise RuntimeError(
            "interrupted identity directory disagrees with frozen schedule"
        )
    if any(
        path.exists()
        for path in (root / "dataset_manifest.json", root / "campaign_completion.json")
    ):
        raise RuntimeError("interrupted campaign unexpectedly has a normal closure")
    dataset = {
        "schema": "AgentTool.V12DuplexP10PreoutcomeCostAbortDataset/1",
        "status": "ABORTED_PREOUTCOME_COST_DECISION",
        "collection_complete": False,
        "frozen_manifest_sha256": sha256(freeze_path),
        "planned_identity_count": len(freeze["identity_manifest"]),
        "attempted_identity_count": len(directories),
        "finalized_session_record_count": len(records),
        "interrupted_partial_identity_count": 1,
        "session_records": records,
        "session_record_inventory_sha256": canonical_sha256(records),
        "interrupted_identity": expected["identity"],
        "interrupted_execution_ordinal": interrupted_ordinal,
        "interrupted_partial_files": partial_files,
        "interrupted_partial_inventory_sha256": canonical_sha256(partial_files),
        "execution_ledger_sha256": sha256(ledger_path),
        "retries": 0,
        "classifier_training": 0,
        "AUC_calculations": 0,
        "class_conditioned_timing_statistics": 0,
    }
    dataset_path = root / "dataset_manifest_preoutcome_cost_abort.json"
    write_new(dataset_path, dataset)
    abort = {
        "schema": "AgentTool.V12DuplexP10PreoutcomeCostAbort/1",
        "status": "ABORTED_PREOUTCOME_COST_DECISION",
        "reason": "USER_DIRECTED_PREOUTCOME_DEVELOPMENT_COST_DECISION",
        "planned_identities": len(freeze["identity_manifest"]),
        "attempted_consumed_identities": len(directories),
        "complete_finalized_sessions": sum(
            row["status"] == "COMPLETE" for row in ledger
        ),
        "failed_finalized_sessions": sum(row["status"] == "FAILED" for row in ledger),
        "interrupted_partial_sessions": 1,
        "interrupted_identity": expected["identity"],
        "retries": 0,
        "all_frozen_identities_permanent_development_exclusions": True,
        "excluded_identity_count": len(freeze["identity_manifest"]),
        "excluded_identity_inventory_sha256": hashlib.sha256(
            "\n".join(sorted(freeze["identity_manifest"])).encode()
        ).hexdigest(),
        "classifier_training": 0,
        "AUC_calculations": 0,
        "class_conditioned_timing_statistics": 0,
        "dataset_manifest_sha256": sha256(dataset_path),
    }
    write_new(root / "campaign_abort_preoutcome_cost_decision.json", abort)
    print(json.dumps(abort, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

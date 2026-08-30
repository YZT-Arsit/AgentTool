from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_exclusive(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.root / "identity_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_dirs = sorted(path for path in (args.root / "raw").iterdir() if path.is_dir())
    class_counts: Counter[str] = Counter()
    framework_complete: Counter[str] = Counter()
    provider_attempts = 0
    failures = []
    evidence_hashes = []
    for raw in raw_dirs:
        result_path = raw / "go_online_result.json"
        if not result_path.is_file():
            failures.append({"raw_directory": raw.name, "failure": "GO_RESULT_ABSENT"})
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        diagnostics = result.get("provider_diagnostics", [])
        provider_attempts += len(diagnostics)
        class_counts.update(str(value.get("class")) for value in diagnostics)
        item_index = int(raw.name.split("-", 1)[0])
        item = manifest["workflows"][item_index]
        if (
            result.get("session_status") == "COMPLETE"
            and len(diagnostics) == 10
            and all(value.get("class") == "PROVIDER_OK" for value in diagnostics)
        ):
            framework_complete[item["framework"]] += 1
        else:
            failures.append(
                {
                    "raw_directory": raw.name,
                    "workflow": item,
                    "session_status": result.get("session_status"),
                    "rounds_emitted": len(result.get("public_relay_events", [])),
                    "schedule_misses": result.get("schedule_misses"),
                    "missed_slots": [
                        value for value in result.get("slot_launches", []) if value.get("schedule_miss")
                    ],
                    "accepted_operation_ids": result.get("accepted_operation_ids", []),
                    "result_operation_ids": [value.get("operation_id") for value in result.get("results", [])],
                    "provider_diagnostics": diagnostics,
                    "pending_operation_ids": result.get("pending_operation_ids", []),
                    "go_result_sha256": sha256(result_path),
                }
            )
        evidence_path = raw / "private_provider_evidence.json"
        if evidence_path.is_file():
            evidence_hashes.append(
                {"raw_directory": raw.name, "sha256": sha256(evidence_path)}
            )
    audit = {
        "schema": "AgentTool.V12ProviderDiagnosticCampaignAudit/1",
        "identity_manifest_sha256": sha256(manifest_path),
        "old_decisive_identity_executed": any(
            "DEV-RC-OA-REPEAT10-007" in path.name for path in raw_dirs
        ),
        "raw_workflows_started": len(raw_dirs),
        "provider_attempts_observed": provider_attempts,
        "provider_diagnostic_class_counts": dict(sorted(class_counts.items())),
        "complete_workflows_by_framework": dict(sorted(framework_complete.items())),
        "failures": failures,
        "private_provider_evidence_hashes": evidence_hashes,
        "retry_performed": False,
        "root_cause_of_retained_v12_rc_provider_error": "NOT_REPRODUCED_UNRESOLVED",
        "campaign_status": "FAIL_NEW_SESSION_SCHEDULE_FAILURE",
        "selected_v12_cases_executed": 0,
    }
    write_json_exclusive(args.output, audit)


if __name__ == "__main__":
    main()

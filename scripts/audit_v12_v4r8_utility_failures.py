from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path
from typing import Any


def read_json(archive: tarfile.TarFile, name: str) -> Any:
    member = archive.extractfile(name)
    if member is None:
        raise FileNotFoundError(name)
    return json.loads(member.read().decode("utf-8"))


def read_jsonl(archive: tarfile.TarFile, name: str) -> list[dict[str, Any]]:
    member = archive.extractfile(name)
    if member is None:
        raise FileNotFoundError(name)
    return [
        json.loads(line)
        for line in member.read().decode("utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite failure audit: {args.output}")
    with tarfile.open(args.archive, "r:gz") as archive:
        roots = sorted(
            {
                name.split("/", 2)[1]
                for name in archive.getnames()
                if name.startswith("runs/") and name.endswith("/utility_record.json")
            }
        )
        rows = []
        for root in roots:
            prefix = f"runs/{root}"
            record = read_json(archive, f"{prefix}/utility_record.json")
            trace = read_json(archive, f"{prefix}/oae_session/go_online_result.json")
            lifecycle = read_json(
                archive, f"{prefix}/oae_session/private_trajectory.json"
            )
            registry = read_jsonl(
                archive,
                f"{prefix}/oae_session/pir/server_visible_trace.jsonl",
            )
            relay = list(trace.get("public_relay_events", []))
            releases = list(trace.get("gateway_response_releases", []))
            submitted = [
                item["operation_id"]
                for item in lifecycle
                if item["stage"] == "ACTION_INTENT_SUBMITTED"
            ]
            delivered = [
                item["operation_id"]
                for item in lifecycle
                if item["stage"] == "FRAMEWORK_RESULT_DELIVERED"
            ]
            accepted = list(trace.get("accepted_operation_ids", []))
            rejected = list(trace.get("resolved_not_admitted_ids", []))
            results = list(trace.get("results", []))
            providers = list(trace.get("provider_diagnostics", []))
            relay_slots = [int(item["round"]) for item in relay]
            public_transcript_success = (
                trace.get("session_status") == "COMPLETE"
                and trace.get("public_transcript_complete") is True
                and len(relay) == 521
                and sorted(relay_slots) == list(range(1, 522))
                and len(registry) == 100
                and sorted(int(item["ordinal"]) for item in registry)
                == list(range(100))
                and len(releases) == 521
                and all(bool(item.get("release_attempted")) for item in releases)
                and all(bool(item.get("response_write_completed")) for item in releases)
            )
            failure_events = [
                item
                for item in lifecycle
                if item["stage"]
                in {"ACTION_REJECTED", "SESSION_FAILURE", "FRAMEWORK_FAILURE"}
            ]
            rows.append(
                {
                    "identity": record["identity"],
                    "ordinal": record["ordinal"],
                    "framework": record["framework"],
                    "workload": record["workload"],
                    "configuration": record["configuration"],
                    "repetition": record["repetition"],
                    "expected_operation_count": 30
                    if record["workload"] == "CACHE_REUSE_30"
                    else 50,
                    "framework_operation_intents_observed": len(submitted),
                    "operations_admitted": len(accepted),
                    "provider_results": len(results),
                    "provider_ok": sum(
                        item.get("class") == "PROVIDER_OK" for item in providers
                    ),
                    "framework_results_delivered": len(delivered),
                    "resolved_not_admitted": len(rejected),
                    "resolved_not_admitted_ids": rejected,
                    "silent_loss": int(trace.get("silent_committed_result_losses", -1)),
                    "profile_overflow": int(trace.get("profile_overflow_events", -1)),
                    "relay_cells": len(relay),
                    "relay_slot_set_complete": sorted(relay_slots)
                    == list(range(1, 522)),
                    "registry_queries": len(registry),
                    "response_release_opportunities": len(releases),
                    "response_release_attempts": sum(
                        bool(item.get("release_attempted")) for item in releases
                    ),
                    "successful_response_writes": sum(
                        bool(item.get("response_write_completed")) for item in releases
                    ),
                    "runtime_session_status": trace.get("session_status"),
                    "public_transcript_complete": trace.get(
                        "public_transcript_complete"
                    ),
                    "public_transcript_success": public_transcript_success,
                    "infrastructure_liveness_failure": trace.get(
                        "infrastructure_liveness_failure"
                    ),
                    "failure_category": record["failure_category"],
                    "exception_string": record["exception_string"],
                    "failure_events": failure_events,
                    "retries": 0,
                }
            )
    output = {
        "schema": "AgentTool.V12V4R8FinalUtilityFailureAudit/1",
        "source_archive": args.archive.name,
        "failed_measured_runs": len(rows),
        "retries": 0,
        "rows": rows,
        "aggregate": {
            "public_transcript_successes": sum(
                row["public_transcript_success"] for row in rows
            ),
            "silent_losses": sum(row["silent_loss"] for row in rows),
            "profile_overflows": sum(row["profile_overflow"] for row in rows),
            "infrastructure_liveness_failures": sum(
                bool(row["infrastructure_liveness_failure"]) for row in rows
            ),
        },
    }
    args.output.write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(output["aggregate"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

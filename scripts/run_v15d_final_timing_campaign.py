from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.collect_v12_p10_timing_sentinel_resume as collector
from v11_online.frameworks import prewarm_framework
from v12_timing.isolated_tasks import build_primary_workload, workload_manifest
from v12_timing.profile import duplex_response_anchor_p10_profile


BASE_V15B = "2cf835cb1e63e1f6f15bfdb523f563ae8608e868"
SEED_LABEL = "V15D-FINAL-TIMING-EVALUATION-20260915"
BLOCK_OFFSET = 90_000
BLOCKS = 80
SPLIT_COUNTS = {"TRAIN": 40, "VALIDATION": 20, "TEST": 20}
COORDINATES = (
    ("TOOL_VS_AGENT_AS_TOOL", "T7", "OpenAI Agents SDK"),
    ("TOOL_VS_AGENT_AS_TOOL", "T7", "Microsoft Agent Framework"),
    ("PROVIDER_READINESS", "T9", "OpenAI Agents SDK"),
    ("PROVIDER_READINESS", "T9", "Microsoft Agent Framework"),
)


def digest(*values: object) -> bytes:
    return hashlib.sha256("|".join(map(str, values)).encode()).digest()


def build(task_id: str, framework: str, label: int, *, planned_block: int):
    return build_primary_workload(
        task_id, framework, label, block=BLOCK_OFFSET + planned_block,
        stage="SENTINEL", delta_ms=10,
    )


def split_for(semantic_task: str, framework: str) -> dict[int, str]:
    order = sorted(range(BLOCKS), key=lambda block: digest(SEED_LABEL, semantic_task, framework, "SPLIT", block))
    output = {}
    start = 0
    for name, count in SPLIT_COUNTS.items():
        for block in order[start:start + count]: output[block] = name
        start += count
    return output


def freeze_manifest() -> dict[str, Any]:
    identities: dict[str, dict[str, Any]] = {}
    schedule = []
    coordinates = []
    ordinal = 0
    for semantic_task, task_id, framework in COORDINATES:
        split = split_for(semantic_task, framework)
        coordinate_id = f"{semantic_task}|{framework}"
        coordinates.append({
            "coordinate_id": coordinate_id, "semantic_task": semantic_task,
            "internal_workload_builder_task": task_id, "framework": framework,
            "observer": "RELAY", "blocks": BLOCKS, "sessions": 2 * BLOCKS,
            "split_blocks": {name: sorted(k for k, value in split.items() if value == name)
                             for name in SPLIT_COUNTS},
        })
        for block in range(BLOCKS):
            members = [build(task_id, framework, label, planned_block=block) for label in (0, 1)]
            class_order = (0, 1) if digest(SEED_LABEL, coordinate_id, block, "ORDER")[0] % 2 == 0 else (1, 0)
            pair_id = hashlib.sha256(f"{SEED_LABEL}|{coordinate_id}|{block}".encode()).hexdigest()[:24]
            for label in class_order:
                workload = members[label]
                row = workload_manifest(workload)
                row.update({
                    "semantic_task": semantic_task, "coordinate_id": coordinate_id,
                    "planned_block": block, "pair_id": pair_id, "partition": split[block],
                    "selection_priority": block,
                    "execution_ordinal": ordinal,
                })
                identities[workload.identity] = row
                schedule.append({"identity": workload.identity, **{key: row[key] for key in (
                    "semantic_task", "coordinate_id", "planned_block", "pair_id", "partition",
                    "selection_priority", "execution_ordinal",
                )}})
                ordinal += 1
    manifest = {
        "schema": "AgentTool.V15DFinalTimingFreeze/1", "base_v15b": BASE_V15B,
        "frozen_before_collection": True, "seed_label": SEED_LABEL,
        "profile": duplex_response_anchor_p10_profile().public_schema(),
        "coordinates": coordinates, "identity_manifest": identities,
        "execution_schedule": schedule, "planned_sessions": len(schedule),
        "splits": SPLIT_COUNTS, "retries": 0,
        "observer": "frozen strengthened Relay application timing projection",
        "excluded_features": ["identity", "label", "private action type", "payload", "status", "absolute wall clock"],
        "paper_facing_task_names": True,
    }
    manifest["payload_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = freeze_manifest()
    (output / "FROZEN_TIMING_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    collector.build_resume_workload = build
    profile = duplex_response_anchor_p10_profile()
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        prewarm_framework(framework)
    records = []
    failures = 0
    stream = (output / "TIMING_SESSION_RECORDS.jsonl").open("x", encoding="utf-8")
    started = time.time_ns()
    try:
        for scheduled in manifest["execution_schedule"]:
            expected = dict(manifest["identity_manifest"][scheduled["identity"]]); expected.update(scheduled)
            ordinal = int(expected["execution_ordinal"])
            unit = output / "sessions" / f'{ordinal:04d}_{expected["identity"]}'
            try:
                record = collector._collect_one(unit, expected, profile=profile)
            except collector.CommonIntegrityFailure as error:
                abort = {"status": "COMMON_INTEGRITY_ABORT", "execution_ordinal": ordinal,
                         "identity": expected["identity"], "error": str(error)}
                (output / "COMMON_INTEGRITY_ABORT.json").write_text(json.dumps(abort, indent=2) + "\n")
                raise
            failures += record["status"] != "COMPLETE"
            record["semantic_task"] = expected["semantic_task"]
            stream.write(json.dumps(record, separators=(",", ":")) + "\n"); stream.flush()
            records.append(record)
            if (ordinal + 1) % 20 == 0:
                print(json.dumps({"completed": ordinal + 1, "failures": failures}), flush=True)
    finally:
        stream.close()
    completion = {
        "schema": "AgentTool.V15DFinalTimingCollection/1", "started_ns": started,
        "ended_ns": time.time_ns(), "planned_sessions": 640,
        "executed_sessions": len(records), "complete_sessions": len(records) - failures,
        "failed_sessions": failures, "retries": 0,
        "collection_complete": len(records) == 640,
        "classifier_fits_during_collection": 0, "auc_calculations_during_collection": 0,
    }
    (output / "TIMING_COLLECTION_COMPLETION.json").write_text(json.dumps(completion, indent=2) + "\n")
    if len(records) != 640: raise SystemExit(2)


if __name__ == "__main__":
    main()

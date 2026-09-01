from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_online.frameworks import prewarm_framework
from v12_timing.controls import run_unprotected_positive_control
from v12_timing.development import run_protected_timing_workload
from v12_timing.isolated_tasks import FRAMEWORKS, TASKS, randomized_pair_order, workload_manifest
from v12_timing.profile import timing_attack_candidate_profiles


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append_ledger(path: Path, row: dict[str, object]) -> str:
    encoded = json.dumps(row, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded + "\n")
    return hashlib.sha256(encoded.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("CONTROL", "SENTINEL", "FULL"), required=True)
    parser.add_argument("--delta", type=int, choices=(0, 10, 20, 25), required=True)
    parser.add_argument("--tasks", nargs="+", choices=tuple(TASKS), required=True)
    parser.add_argument("--block-start", type=int, required=True)
    parser.add_argument("--block-count", type=int, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite timing campaign: {args.output}")
    if (args.mode == "CONTROL") != (args.delta == 0):
        raise ValueError("positive controls use Delta=0; protected campaigns require a frozen Delta")
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    seed_hex = str(freeze["block_randomization_seed_sha256"])
    profiles = {profile.round_period_ms: profile for profile in timing_attack_candidate_profiles()}
    profile = None if args.mode == "CONTROL" else profiles[args.delta]
    identities: list[dict[str, object]] = []
    for task_id in args.tasks:
        for framework in FRAMEWORKS:
            for block in range(args.block_start, args.block_start + args.block_count):
                identities.extend(
                    workload_manifest(item)
                    for item in randomized_pair_order(
                        task_id,
                        framework,
                        block=block,
                        stage=args.mode,
                        delta_ms=args.delta,
                        seed_hex=seed_hex,
                    )
                )
    expected_sessions = len(identities)
    if len({str(item["identity"]) for item in identities}) != expected_sessions:
        raise AssertionError("campaign generator produced duplicate identities")
    args.output.mkdir(parents=True)
    manifest = {
        "schema": "AgentTool.V12IsolatedTimingCampaignManifest/1",
        "freeze_sha256": sha(args.freeze),
        "mode": args.mode,
        "delta_ms": args.delta,
        "profile_id": profile.profile_id if profile is not None else "UNPROTECTED_CONTROL",
        "tasks": args.tasks,
        "frameworks": list(FRAMEWORKS),
        "block_start": args.block_start,
        "block_count": args.block_count,
        "expected_sessions": expected_sessions,
        "identities": identities,
        "retry": "PROHIBITED",
        "replacement": "PROHIBITED",
        "started_ns": time.time_ns(),
    }
    manifest_path = args.output / "campaign_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    ledger = args.output / "execution_ledger.jsonl"
    previous = "0" * 64
    completed = 0
    current_framework = None
    for item in identities:
        workload = randomized_pair_order(
            str(item["task_id"]),
            str(item["framework"]),
            block=int(item["block"]),
            stage=args.mode,
            delta_ms=args.delta,
            seed_hex=seed_hex,
        )
        workload = next(value for value in workload if value.label == int(item["label"]))
        if current_framework != workload.framework:
            prewarm_framework(workload.framework)
            current_framework = workload.framework
        session_root = args.output / "sessions" / f"{completed:06d}_{workload.identity}"
        started = time.time_ns()
        try:
            if args.mode == "CONTROL":
                record = run_unprotected_positive_control(workload)
                session_root.mkdir(parents=True)
                record_path = session_root / "isolated_timing_record.json"
                record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
            else:
                assert profile is not None
                record = run_protected_timing_workload(session_root, workload, profile)
                record_path = session_root / "isolated_timing_record.json"
            if not record["functional"]:
                raise RuntimeError(f"timing session functional failure: {record.get('failures', [])}")
            ledger_row: dict[str, object] = {
                "index": completed,
                "identity": workload.identity,
                "task_id": workload.task_id,
                "framework": workload.framework,
                "label": workload.label,
                "block": workload.block,
                "started_ns": started,
                "ended_ns": time.time_ns(),
                "record_path": str(record_path.relative_to(args.output)),
                "record_sha256": sha(record_path),
                "functional": True,
                "previous_record_sha256": previous,
            }
        except BaseException as exc:
            failure = {
                "schema": "AgentTool.V12IsolatedTimingCampaignFailure/1",
                "index": completed,
                "identity": workload.identity,
                "task_id": workload.task_id,
                "framework": workload.framework,
                "label": workload.label,
                "block": workload.block,
                "started_ns": started,
                "ended_ns": time.time_ns(),
                "exception_class": type(exc).__name__,
                "exception_string": str(exc),
                "traceback": traceback.format_exc(),
                "retry_count": 0,
                "replacement_count": 0,
            }
            failure_path = args.output / "campaign_failure.json"
            failure_path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8", newline="\n")
            ledger_row = {
                "index": completed,
                "identity": workload.identity,
                "functional": False,
                "failure_sha256": sha(failure_path),
                "previous_record_sha256": previous,
            }
            previous = append_ledger(ledger, ledger_row)
            return 2
        previous = append_ledger(ledger, ledger_row)
        completed += 1
    completion = {
        "schema": "AgentTool.V12IsolatedTimingCampaignCompletion/1",
        "manifest_sha256": sha(manifest_path),
        "status": "PASS",
        "completed_sessions": completed,
        "expected_sessions": expected_sessions,
        "ledger_sha256": sha(ledger),
        "last_ledger_record_sha256": previous,
        "ended_ns": time.time_ns(),
        "retry_count": 0,
        "replacement_count": 0,
        "timing_confirmatory_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    (args.output / "campaign_completion.json").write_text(
        json.dumps(completion, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

from scripts.run_v12_pir_capacity_development import run_one
from v12_timing.profile import causal_horizon_candidate_profiles


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append_ledger(path: Path, record: dict[str, object]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded + "\n")
    return hashlib.sha256(encoded.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite causal-horizon live root: {output}")
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profiles = {profile.admission_horizon_ms: profile for profile in causal_horizon_candidate_profiles()}
    forbidden = set(manifest["forbidden_identities"])
    seen: set[str] = set()
    for candidate in manifest["candidates"]:
        for item in candidate["workloads"]:
            identity = str(item["identity"])
            if identity in forbidden or identity in seen:
                raise ValueError(f"forbidden or duplicate live identity: {identity}")
            seen.add(identity)
    output.mkdir(parents=True)
    ledger = output / "execution_ledger.jsonl"
    previous = "0" * 64
    index = 0
    selected_horizon = None
    candidate_results: list[dict[str, object]] = []
    for candidate in manifest["candidates"]:
        horizon = int(candidate["horizon_ms"])
        profile = profiles[horizon]
        candidate_record: dict[str, object] = {
            "horizon_ms": horizon,
            "profile_id": profile.profile_id,
            "status": "IN_PROGRESS",
            "workloads": [],
        }
        for item in candidate["workloads"]:
            started = time.time_ns()
            identity = str(item["identity"])
            unit_root = output / f"H{horizon}" / f"{index:02d}_{identity}"
            try:
                verdict = run_one(unit_root, item, profile)
                passed = bool(verdict["passed"])
                unit_record: dict[str, object] = {
                    "index": index,
                    "horizon_ms": horizon,
                    "identity": identity,
                    "kind": item["kind"],
                    "framework": item["framework"],
                    "started_ns": started,
                    "ended_ns": time.time_ns(),
                    "passed": passed,
                    "verdict_sha256": sha(unit_root / "capacity_verdict.json"),
                    "previous_record_sha256": previous,
                }
            except BaseException as exc:
                failure = {
                    "schema": "AgentTool.V12CausalHorizonLiveFailure/1",
                    "index": index,
                    "horizon_ms": horizon,
                    "identity": identity,
                    "kind": item["kind"],
                    "framework": item["framework"],
                    "started_ns": started,
                    "ended_ns": time.time_ns(),
                    "exception_class": type(exc).__name__,
                    "exception_string": str(exc),
                    "traceback": traceback.format_exc(),
                    "retry_count": 0,
                    "replacement_count": 0,
                    "timing_attack_session": False,
                }
                failure_path = output / f"H{horizon}" / f"failure_{index:02d}_{identity}.json"
                failure_path.parent.mkdir(parents=True, exist_ok=True)
                failure_path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8", newline="\n")
                passed = False
                unit_record = {
                    "index": index,
                    "horizon_ms": horizon,
                    "identity": identity,
                    "kind": item["kind"],
                    "framework": item["framework"],
                    "started_ns": started,
                    "ended_ns": failure["ended_ns"],
                    "passed": False,
                    "failure_sha256": sha(failure_path),
                    "previous_record_sha256": previous,
                }
            previous = append_ledger(ledger, unit_record)
            candidate_record["workloads"].append(unit_record)
            index += 1
            if not passed:
                candidate_record["status"] = "FAIL"
                candidate_record["first_failure_identity"] = identity
                break
        else:
            candidate_record["status"] = "PASS"
            selected_horizon = horizon
        candidate_results.append(candidate_record)
        (output / f"H{horizon}" / "candidate_verdict.json").write_text(
            json.dumps(candidate_record, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        if selected_horizon is not None:
            break

    completion = {
        "schema": "AgentTool.V12CausalHorizonLiveCompletion/1",
        "manifest_sha256": sha(manifest_path),
        "candidate_results": candidate_results,
        "selected_causal_horizon_ms": selected_horizon if selected_horizon is not None else "NONE",
        "status": "PASS" if selected_horizon is not None else "CAUSAL_HORIZON_NO_GO",
        "executed_units": index,
        "retry_count": 0,
        "replacement_count": 0,
        "final_ledger_record_sha256": previous,
        "ledger_sha256": sha(ledger),
        "timing_attack_sessions": 0,
        "timing_confirmatory_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    (output / "campaign_completion.json").write_text(
        json.dumps(completion, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return 0 if selected_horizon is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())

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
from v12_timing.profile import timing_attack_candidate_profiles


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite V3 functional capacity root: {args.output}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    profiles = {profile.round_period_ms: profile for profile in timing_attack_candidate_profiles()}
    forbidden = tuple(manifest["forbidden_identity_prefixes"])
    identities = [item["identity"] for candidate in manifest["candidates"] for item in candidate["workloads"]]
    if len(identities) != len(set(identities)) or any(identity.startswith(forbidden) for identity in identities):
        raise ValueError("V3 capacity manifest contains duplicate or forbidden identity")
    args.output.mkdir(parents=True)
    ledger = args.output / "execution_ledger.jsonl"
    previous = "0" * 64
    results: list[dict[str, object]] = []
    index = 0
    for candidate in manifest["candidates"]:
        delta = int(candidate["delta_ms"])
        profile = profiles[delta]
        candidate_result: dict[str, object] = {"delta_ms": delta, "profile_id": profile.profile_id, "workloads": []}
        for item in candidate["workloads"]:
            unit = args.output / f"P{delta}" / f"{index:02d}_{item['identity']}"
            started = time.time_ns()
            try:
                verdict = run_one(unit, item, profile)
                passed = bool(verdict["passed"])
                row: dict[str, object] = {
                    "index": index,
                    "delta_ms": delta,
                    "identity": item["identity"],
                    "framework": item["framework"],
                    "kind": item["kind"],
                    "passed": passed,
                    "started_ns": started,
                    "ended_ns": time.time_ns(),
                    "verdict_sha256": sha(unit / "capacity_verdict.json"),
                    "previous_record_sha256": previous,
                }
            except BaseException as exc:
                failure = {
                    "schema": "AgentTool.V12TimingV3FunctionalFailure/1",
                    "index": index,
                    "delta_ms": delta,
                    "identity": item["identity"],
                    "exception_class": type(exc).__name__,
                    "exception_string": str(exc),
                    "traceback": traceback.format_exc(),
                    "retry_count": 0,
                    "replacement_count": 0,
                }
                failure_path = args.output / f"P{delta}" / "candidate_failure.json"
                failure_path.parent.mkdir(parents=True, exist_ok=True)
                failure_path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8", newline="\n")
                passed = False
                row = {
                    "index": index,
                    "delta_ms": delta,
                    "identity": item["identity"],
                    "passed": False,
                    "failure_sha256": sha(failure_path),
                    "previous_record_sha256": previous,
                }
            encoded = json.dumps(row, sort_keys=True, separators=(",", ":"))
            with ledger.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded + "\n")
            previous = hashlib.sha256(encoded.encode()).hexdigest()
            candidate_result["workloads"].append(row)
            index += 1
            if not passed:
                break
        candidate_result["status"] = "PASS" if len(candidate_result["workloads"]) == 8 and all(row["passed"] for row in candidate_result["workloads"]) else "CANDIDATE_FUNCTIONAL_FAIL"
        results.append(candidate_result)
    completion = {
        "schema": "AgentTool.V12TimingV3FunctionalCapacityCompletion/1",
        "manifest_sha256": sha(args.manifest),
        "candidate_results": results,
        "executed_units": index,
        "all_candidates_functional": all(item["status"] == "PASS" for item in results),
        "ledger_sha256": sha(ledger),
        "last_ledger_record_sha256": previous,
        "retry_count": 0,
        "replacement_count": 0,
        "timing_attack_sessions": 0,
        "timing_confirmatory_sessions": 0,
    }
    (args.output / "campaign_completion.json").write_text(
        json.dumps(completion, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return 0 if completion["all_candidates_functional"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

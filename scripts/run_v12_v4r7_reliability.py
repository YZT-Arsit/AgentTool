from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v12_duplex_response_reliability import run_one
from v12_timing.profile import duplex_provider_bound_p10_profile


FREEZE = ROOT / "V12_V4R7_PROVIDER_BOUND_CLOSURE_FREEZE.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, default=FREEZE)
    args = parser.parse_args()
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    identities = list(freeze["synthetic_reliability_identities"])
    if len(identities) != 200 or len(set(identities)) != 200:
        raise RuntimeError("V4R7 reliability identity freeze is malformed")
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    ledger = args.output / "execution_ledger.jsonl"
    profile = duplex_provider_bound_p10_profile()
    for ordinal, identity in enumerate(identities, start=1):
        record = run_one(args.runner, args.output, identity, profile=profile)
        runtime = json.loads(
            (args.output / identity / "go_online_result.json").read_text(
                encoding="utf-8"
            )
        )
        record["checks"]["zero_semantic_provider_timeouts"] = all(
            row.get("class") != "PROVIDER_CONTEXT_DEADLINE_EXCEEDED"
            for row in runtime.get("provider_diagnostics", [])
        )
        record["pass"] = all(record["checks"].values())
        record["ordinal"] = ordinal
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        records.append(record)
        if not bool(record["pass"]):
            break
    passed = sum(bool(record["pass"]) for record in records)
    summary = {
        "schema": "AgentTool.V12V4R7SyntheticReliability/1",
        "profile_id": profile.profile_id,
        "rounds": profile.total_rounds,
        "planned_sessions": 200,
        "executed_sessions": len(records),
        "passed_sessions": passed,
        "failed_sessions": len(records) - passed,
        "retries": 0,
        "protected_classifier_runs": 0,
        "protected_auc_calculations": 0,
        "status": "PASS" if passed == 200 else "FAIL",
        "records": records,
    }
    (args.output / "SYNTHETIC_RELIABILITY_SUMMARY.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.delta_capacity import audit_delta_capacity
from v12_timing.profile import delta_functional_candidate_profiles


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    freeze = ROOT / "V12_APPLICATION_OBSERVABILITY_DELTA_CANDIDATES_FREEZE.json"
    results = [audit_delta_capacity(profile) for profile in delta_functional_candidate_profiles()]
    payload = {
        "schema": "AgentTool.V12ApplicationObservabilityCapacityFreeze/1",
        "candidate_freeze_sha256": sha(freeze),
        "mode": "STATIC_DETERMINISTIC_NO_WORKLOAD_EXECUTION",
        "results": results,
        "all_candidates_mechanically_eligible": all(bool(row["passed"]) for row in results),
        "classifier_training_runs": 0, "real_auc_calculations": 0,
    }
    output = ROOT / "V12_APPLICATION_OBSERVABILITY_CAPACITY_FREEZE.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if payload["all_candidates_mechanically_eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

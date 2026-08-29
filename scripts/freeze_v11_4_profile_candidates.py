from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_4.profile import (
    HORIZON_CANDIDATES_MS,
    PERIOD_CANDIDATES_MS,
    PERIOD_QUALIFICATION_HORIZON_MS,
    period_candidate_profiles,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != value:
            raise FileExistsError(f"refusing to overwrite a different V11.4 pre-execution freeze: {path}")
        return
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    v113_csv = ROOT / "CAUSAL_DEPTH_QUALIFICATION_V11_3.csv"
    rows = list(csv.DictReader(v113_csv.open(encoding="utf-8")))
    if len(rows) != 1000:
        raise AssertionError("V11.3 immutable qualification evidence is not 1,000 rows")
    strata: dict[str, dict[str, dict[str, int]]] = {}
    for admission in (75, 100, 150, 200, 300):
        key = str(admission)
        strata[key] = {}
        for count in (10, 20, 30, 50):
            subset = [r for r in rows if int(r["admission_rounds"]) == admission and r["group"] == f"CAUSAL_{count}"]
            strata[key][str(count)] = {
                "passed": sum(r["passed"].lower() == "true" for r in subset),
                "total": len(subset),
            }
    negative = {
        "schema": "AgentTool.V11_3NegativeProfileFreezeForV11_4/1",
        "classification": "IMMUTABLE_NEGATIVE_DEVELOPMENT_EVIDENCE",
        "v11_2": {
            "passed": 17,
            "total": 20,
            "profile_admission_closed": 3,
            "source": "V11_2_ONLINE_DEVELOPMENT_FREEZE_V11_3.json",
            "source_sha256": sha256(ROOT / "V11_2_ONLINE_DEVELOPMENT_FREEZE_V11_3.json"),
        },
        "v11_3": {
            "sessions": len(rows),
            "no_retries": True,
            "strata": strata,
            "scheduler_exact": sum(int(r["schedule_misses"]) == 0 and int(r["rounds"]) > 0 for r in rows),
            "scheduler_misses": sum(int(r["schedule_misses"]) for r in rows),
            "profile_overflow": sum(int(r["profile_overflow"]) for r in rows),
            "dummy_heavy_operations": sum(int(r["dummy_heavy_ops"]) for r in rows),
            "silent_committed_result_loss": sum(int(r["silent_committed_result_loss"]) for r in rows),
            "source": v113_csv.name,
            "source_sha256": sha256(v113_csv),
            "root_causes": [
                "ONLINE_ADMISSION_HORIZON_TOO_SHORT",
                "FIVE_MS_SCHEDULER_NOT_FINAL_PROFILE_QUALIFIED",
            ],
        },
        "old_v10_selected_outcomes_observed": False,
        "v10_1_selected_outcomes_observed": False,
    }
    write_json(ROOT / "V11_3_NEGATIVE_PROFILE_FREEZE_V11_4.json", negative)

    candidates = {
        "schema": "AgentTool.V11_4PublicPeriodCandidates/1",
        "development_only": True,
        "candidate_order_ms": list(PERIOD_CANDIDATES_MS),
        "period_qualification_horizon_ms": PERIOD_QUALIFICATION_HORIZON_MS,
        "sessions_per_candidate": 500,
        "selection_rule": "smallest period in ascending predeclared order passing all 500 sessions; stop after first pass",
        "profiles": [profile.public_schema() for profile in period_candidate_profiles()],
        "future_horizon_candidate_order_ms": list(HORIZON_CANDIDATES_MS),
        "timing_privacy": "OPEN / NOT TESTED",
        "packet_level_timing": "OPEN",
    }
    write_json(ROOT / "PUBLIC_PERIOD_CANDIDATES_V11_4.json", candidates)

    model = """# V11.4 public profile model

V11.4 qualifies, but does not redesign, the V11 online architecture. The public profile is `Gamma(M,H,Delta,B,D,T,...)`, selected before private execution. It defines `A=ceil(H/Delta)`, `C=ceil(B/Delta)`, `D=M`, and `R=A+C+M+T` for the current one-result-per-response architecture. The qualification fixes `M=50`, `B=50 ms`, and `T=1` after period selection.

The privacy-facing structural contract is parametric: the same `Gamma` produces the same session count, endpoint classes, HTTP/2 reuse policy, round count/order, OHTTP suite, and request/response size sequences. Private action count, identity, target, kind, causal depth, repetition, frequency, and placement do not create slots or extend the horizon. An action becoming ready after `H` is rejected with `PROFILE_ADMISSION_CLOSED`.

Qualification is sequential and predeclared. Stage P tests 10, 20, and 25 ms on a public 1,000 ms, one-operation, NOOP-heavy profile and freezes the first 500/500 candidate. Stage H then tests 2,000, 3,000, 4,000, 5,000, 7,500, and 10,000 ms in ascending order using the frozen period. No two-dimensional tuning or post-result candidate addition is permitted.

This is scheduler/transport reliability engineering, not a timing-privacy test. `TIMING_PRIVACY = OPEN / NOT TESTED`; packet-level timing remains open.
"""
    path = ROOT / "PUBLIC_PROFILE_MODEL_V11_4.md"
    if path.exists() and path.read_text(encoding="utf-8") != model:
        raise FileExistsError(f"refusing to overwrite a different model freeze: {path}")
    path.write_text(model, encoding="utf-8")

    freeze = {
        "schema": "AgentTool.V11_4PreQualificationFreeze/1",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "stage_order": ["PERIOD", "HORIZON", "POST_SELECTION"],
        "period_candidates_ms": list(PERIOD_CANDIDATES_MS),
        "period_sessions_each": 500,
        "period_qualification_horizon_ms": PERIOD_QUALIFICATION_HORIZON_MS,
        "horizon_candidates_ms": list(HORIZON_CANDIDATES_MS),
        "horizon_counts": {"10": 100, "20": 50, "30": 30, "50": 30},
        "files_sha256": {
            name: sha256(ROOT / name)
            for name in (
                "v11_4/profile.py",
                "v11_online/session.py",
                "scripts/freeze_v11_4_profile_candidates.py",
                "V11_3_NEGATIVE_PROFILE_FREEZE_V11_4.json",
                "PUBLIC_PERIOD_CANDIDATES_V11_4.json",
                "PUBLIC_PROFILE_MODEL_V11_4.md",
            )
        },
        "holdout_selected_or_executed": False,
        "seed_search": False,
    }
    write_json(ROOT / "V11_4_FINAL_QUALIFICATION_PREEXECUTION_FREEZE.json", freeze)


if __name__ == "__main__":
    main()

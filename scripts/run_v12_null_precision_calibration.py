from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.planning import (
    BASE_EVAL_BLOCK_CANDIDATES,
    EXTENDED_EVAL_BLOCK_CANDIDATES,
    PLANNING_SUCCESS_PROBABILITY,
    PROTECTED_UCB_LIMIT,
    calibrate_null_candidate,
    derive_block_denominator,
    protected_execution_cost,
)
from v12_timing.statistics import BOOTSTRAP_RESAMPLES


def _candidate(arguments: tuple[int, int, int, int]) -> dict[str, float | int]:
    count, trials, resamples, seed = arguments
    return calibrate_null_candidate(
        count, trials=trials, bootstrap_resamples=resamples, seed=seed
    )


def _run_counts(
    counts: tuple[int, ...], *, trials: int, resamples: int, seed: int, workers: int
) -> list[dict[str, float | int]]:
    arguments = [(count, trials, resamples, seed) for count in counts]
    if workers == 1:
        rows = [_candidate(value) for value in arguments]
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(_candidate, arguments))
    return sorted(rows, key=lambda row: int(row["eval_blocks"]))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Artificial-score-only V12 null precision planning; reads no project traces."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=250)
    parser.add_argument("--bootstrap-resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    parser.add_argument("--seed", type=int, default=120260831)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing evidence: {args.output}")
    if args.trials < 1 or args.bootstrap_resamples != BOOTSTRAP_RESAMPLES:
        raise SystemExit("decisive planning requires positive trials and exactly 10,000 bootstraps")

    rows = _run_counts(
        BASE_EVAL_BLOCK_CANDIDATES,
        trials=args.trials,
        resamples=args.bootstrap_resamples,
        seed=args.seed,
        workers=args.workers,
    )
    passing = [row for row in rows if row["planning_criterion_pass"]]
    extended = False
    if not passing:
        extended = True
        rows.extend(
            _run_counts(
                EXTENDED_EVAL_BLOCK_CANDIDATES,
                trials=args.trials,
                resamples=args.bootstrap_resamples,
                seed=args.seed,
                workers=args.workers,
            )
        )
        passing = [row for row in rows if row["planning_criterion_pass"]]
    if not passing:
        raise SystemExit("no planned denominator satisfies the frozen criterion through 1,000")
    selected = min(int(row["eval_blocks"]) for row in passing)
    result = {
        "schema": "AgentTool.V12TimingNullPrecisionCalibration/1",
        "input_kind": "ARTIFICIAL_NUMERIC_SCORE_ARRAYS_ONLY",
        "reads_project_traces": False,
        "true_auc": 0.5,
        "bootstrap_unit": "COMPLETE_MATCHED_EVAL_BLOCK",
        "bootstrap_resamples": args.bootstrap_resamples,
        "one_sided_ucb_percentile": 95,
        "protected_ucb_limit": PROTECTED_UCB_LIMIT,
        "required_probability": PLANNING_SUCCESS_PROBABILITY,
        "outer_null_trials": args.trials,
        "seed": args.seed,
        "extended_beyond_500": extended,
        "results": sorted(rows, key=lambda row: int(row["eval_blocks"])),
        "selected_eval_blocks": selected,
        "denominator": derive_block_denominator(selected),
        "protected_execution_cost": protected_execution_cost(selected),
        "protected_trace_sessions_read": 0,
        "protected_classifier_training_runs": 0,
        "protected_real_auc_calculations": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

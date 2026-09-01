from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.controls import run_all_synthetic_timing_pipeline_controls
from v12_timing.statistics import BOOTSTRAP_RESAMPLES


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fixed-dimension artificial V12 timing pipeline control; reads no project traces."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=120260831)
    parser.add_argument("--bootstrap-resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing evidence: {args.output}")
    if args.bootstrap_resamples != BOOTSTRAP_RESAMPLES:
        raise SystemExit("closure control requires exactly 10,000 bootstrap resamples")
    result = run_all_synthetic_timing_pipeline_controls(
        seed=args.seed, bootstrap_resamples=args.bootstrap_resamples
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

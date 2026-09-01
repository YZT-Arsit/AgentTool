from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import analyze_v12_p10_timing_sentinel_resume as implementation

from v12_timing.sentinel_v3 import (
    TARGET_EVAL_COMPLETE_BLOCKS,
    TARGET_TRAIN_COMPLETE_BLOCKS,
    TOTAL_SESSIONS,
    completion_channel,
    select_complete_blocks,
    validate_freeze_manifest,
)

implementation.TOTAL_SESSIONS = TOTAL_SESSIONS
implementation.TARGET_TRAIN_COMPLETE_BLOCKS = TARGET_TRAIN_COMPLETE_BLOCKS
implementation.TARGET_EVAL_COMPLETE_BLOCKS = TARGET_EVAL_COMPLETE_BLOCKS
implementation.completion_channel = completion_channel
implementation.select_complete_blocks = select_complete_blocks
implementation.validate_freeze_manifest = validate_freeze_manifest
implementation.ANALYSIS_SCHEMA = "AgentTool.V12P10TimingSentinelV3Analysis/1"
implementation.ANALYSIS_PHASE = "V12-P10-TIMING-DISTINGUISHABILITY-SENTINEL-V3"
implementation.ANALYSIS_FILENAME = "sentinel_v3_analysis.json"
implementation.COMPARISONS_FILENAME = "observer_comparisons_v3.csv"


def _paper_summary(output: Path) -> None:
    report_path = output / implementation.ANALYSIS_FILENAME
    report = json.loads(report_path.read_text(encoding="utf-8"))
    comparisons = [
        {
            "task": row["task_id"],
            "observer": row["observer"],
            "framework": row["framework"],
            "eval_auc": row.get("eval_point_auc"),
            "lcb99_5": row.get("eval_lcb99_5_one_sided"),
            "ci95_low": row.get("eval_ci95_two_sided_low"),
            "ci95_high": row.get("eval_ci95_two_sided_high"),
            "selected_model": row.get("selected_train_model"),
            "status": row["status"],
        }
        for row in report["observer_comparisons"]
    ]
    worst: dict[str, float] = {}
    for row in comparisons:
        if row["status"] == "EVALUATED" and row["eval_auc"] is not None:
            task = str(row["task"])
            worst[task] = max(worst.get(task, 0.0), float(row["eval_auc"]))
    summary = {
        "schema": "AgentTool.V12P10TimingSentinelV3PaperPlanning/1",
        "role": "DEVELOPMENT_ONLY_NOT_FINAL_PAPER_EVIDENCE",
        "comparisons": comparisons,
        "worst_point_auc_by_task": worst,
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
    }
    implementation.write_json(output / "paper_planning_summary.json", summary)
    with (output / "paper_planning_summary.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(comparisons[0]) if comparisons else ())
        if comparisons:
            writer.writeheader()
            writer.writerows(comparisons)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output", type=Path, required=True)
    known, _ = parser.parse_known_args()
    result = implementation.main()
    if result == 0:
        _paper_summary(known.output)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

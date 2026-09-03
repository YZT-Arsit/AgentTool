from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import analyze_v12_v4r7_late_frame_smoke as implementation

from v12_timing.sentinel_smoke_v4r8 import (
    BOOTSTRAP_RESAMPLES,
    RANDOMIZATION_RESAMPLES,
    SMOKE_FAILURE_MARGIN,
    SMOKE_LCB_QUANTILE,
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
implementation.implementation.TOTAL_SESSIONS = TOTAL_SESSIONS
implementation.implementation.TARGET_TRAIN_COMPLETE_BLOCKS = (
    TARGET_TRAIN_COMPLETE_BLOCKS
)
implementation.implementation.TARGET_EVAL_COMPLETE_BLOCKS = TARGET_EVAL_COMPLETE_BLOCKS
implementation.implementation.completion_channel = completion_channel
implementation.implementation.select_complete_blocks = select_complete_blocks
implementation.implementation.validate_freeze_manifest = validate_freeze_manifest
implementation.implementation.SENTINEL_BOOTSTRAP_RESAMPLES = BOOTSTRAP_RESAMPLES
implementation.implementation.SENTINEL_RANDOMIZATION_RESAMPLES = RANDOMIZATION_RESAMPLES
implementation.implementation.SENTINEL_LCB_QUANTILE = SMOKE_LCB_QUANTILE
implementation.implementation.SENTINEL_EARLY_FAIL_MARGIN = SMOKE_FAILURE_MARGIN

V4R7_RELAY_AUCS = {
    ("T7", "OpenAI Agents SDK", "RELAY"): 0.4855555555555555,
    ("T7", "Microsoft Agent Framework", "RELAY"): 0.6711111111111111,
    ("T9", "OpenAI Agents SDK", "RELAY"): 0.6844444444444444,
    ("T9", "Microsoft Agent Framework", "RELAY"): 0.4688888888888889,
}


def _output_from_arguments() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output", type=Path, required=True)
    args, _ = parser.parse_known_args(sys.argv[1:])
    return args.output


def _add_v4r8_ablation(output: Path) -> None:
    path = output / "duplex_repair_smoke_analysis.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for result in report["observer_comparisons"]:
        key = (result["task_id"], result["framework"], result["observer"])
        if key not in V4R7_RELAY_AUCS or result["status"] != "EVALUATED":
            continue
        historical = next(
            row["historical_one_sided_P10_AUC"]
            for row in report["historical_one_sided_vs_duplex_smoke"]
            if (row["task"], row["framework"], row["observer"]) == key
        )
        rows.append(
            {
                "task": key[0],
                "framework": key[1],
                "observer": key[2],
                "historical_one_sided_AUC": historical,
                "V4R7_AUC": V4R7_RELAY_AUCS[key],
                "V4R8_AUC": result["eval_point_auc"],
                "datasets_combined": False,
                "role": "POST_OUTCOME_DEVELOPMENT_ABLATION_ONLY",
            }
        )
    report.update(
        {
            "schema": "AgentTool.V12V4R8ResponseAnchorSmokeAnalysis/1",
            "phase": "V12-V4R8-RESPONSE-PUBLIC-ANCHOR-REPAIR",
            "runtime_revision": "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R8",
            "targeted_change": "REMOVE_GATEWAY_REQUEST_ARRIVAL_FROM_PLANNED_RESPONSE_CLOCK",
            "development_ablation": rows,
        }
    )
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    output = _output_from_arguments()
    status = implementation.implementation.main()
    if status == 0:
        _add_v4r8_ablation(output)
    raise SystemExit(status)

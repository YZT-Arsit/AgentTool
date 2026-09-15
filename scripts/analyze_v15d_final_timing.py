from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_v15d_access_privacy import binary_attack
from v12_timing.projection import expected_raw_timing_widths, timing_feature_vector


HISTORICAL = {
    ("TOOL_VS_AGENT_AS_TOOL", "OpenAI Agents SDK"): (0.980763888888889, 0.9681232638888889, 0.9909739583333333, 0.00009999000099990002),
    ("TOOL_VS_AGENT_AS_TOOL", "Microsoft Agent Framework"): (0.9693055555555555, 0.9468055555555556, 0.9875694444444445, 0.00009999000099990002),
    ("PROVIDER_READINESS", "OpenAI Agents SDK"): (0.9779861111111111, 0.9579166666666666, 0.9930555555555556, 0.00009999000099990002),
    ("PROVIDER_READINESS", "Microsoft Agent Framework"): (0.9902777777777778, 0.9809027777777778, 0.9969444444444444, 0.00009999000099990002),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); campaign = args.campaign.resolve(); output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((campaign / "FROZEN_TIMING_MANIFEST.json").read_text())
    records = [json.loads(line) for line in (campaign / "TIMING_SESSION_RECORDS.jsonl").read_text().splitlines() if line]
    record_by_id = {row["identity"]: row for row in records}
    widths = expected_raw_timing_widths("RELAY", public_r=521, public_q=100, has_relay_duplex=True)
    final_rows = []
    failure_channels = []
    for coordinate in manifest["coordinates"]:
        coordinate_id = coordinate["coordinate_id"]
        identities = [row for row in manifest["identity_manifest"].values() if row["coordinate_id"] == coordinate_id]
        by_block = defaultdict(list)
        for frozen in identities: by_block[int(frozen["planned_block"])].append(frozen)
        complete_blocks = []
        for block, members in by_block.items():
            observed = [record_by_id.get(member["identity"]) for member in members]
            complete = len(observed) == 2 and all(row and row["status"] == "COMPLETE" and row["timing_classifier_eligible"] for row in observed)
            if complete: complete_blocks.append(block)
            else:
                failure_channels.append({"coordinate_id": coordinate_id, "planned_block": block,
                                         "member_statuses": [None if row is None else row["status"] for row in observed]})
        x, y, splits, groups = [], [], [], []
        for frozen in sorted(identities, key=lambda row: (int(row["planned_block"]), int(row["label"]))):
            if int(frozen["planned_block"]) not in complete_blocks: continue
            record = record_by_id[frozen["identity"]]
            x.append(timing_feature_vector(record["observer_projections"]["RELAY"], raw_widths=widths))
            y.append(int(frozen["label"])); splits.append(frozen["partition"]); groups.append(int(frozen["planned_block"]))
        result = binary_attack(coordinate["semantic_task"], "FINAL_OAE_RELAY_TIMING", np.asarray(x),
                               np.asarray(y), np.asarray(splits), np.asarray(groups))
        result.update({
            "framework": coordinate["framework"], "observer": "RELAY",
            "condition": "FINAL_OAE_BIDIRECTIONAL_SHAPING",
            "complete_matched_blocks": len(complete_blocks),
            "failed_matched_blocks": 80 - len(complete_blocks),
        })
        final_rows.append(result)
        auc, low, high, p = HISTORICAL[(coordinate["semantic_task"], coordinate["framework"])]
        final_rows.append({
            "experiment": coordinate["semantic_task"], "framework": coordinate["framework"],
            "observer": "RELAY", "condition": "HISTORICAL_ONE_SIDED_POSITIVE_CONTROL",
            "selected_model": "HIST_GRADIENT_BOOSTING", "test_raw_auc": auc,
            "test_train_oriented_auc": auc, "test_orientation_invariant_auc": max(auc, 1 - auc),
            "ci95_low": low, "ci95_high": high, "permutation_p": p,
            "n_train": 180, "n_test": 120,
            "source": "V12_P10_TIMING_ANALYSIS_V3_1_EVIDENCE/observer_comparisons_v3_1.csv",
            "historical_component_control": True,
        })
    keys = sorted({key for row in final_rows for key in row})
    with (output / "FINAL_TIMING_RESULTS.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys); writer.writeheader(); writer.writerows(final_rows)
    strongest = max((row for row in final_rows if row["condition"] == "FINAL_OAE_BIDIRECTIONAL_SHAPING"),
                    key=lambda row: row["test_orientation_invariant_auc"])
    summary = {
        "schema": "AgentTool.V15DFinalTimingStatistics/1", "rows": final_rows,
        "failure_channel": failure_channels, "strongest_final": strongest,
        "timing_privacy": "NOT_ESTABLISHED" if strongest["ci95_low"] > .5 else "NOT_ESTABLISHED",
        "claim_boundary": "No realized-timing indistinguishability claim; every residual is preserved.",
    }
    (output / "TIMING_STATISTICAL_SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()

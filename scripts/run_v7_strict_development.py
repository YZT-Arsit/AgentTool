"""Paired STRICT development runs. These are not confirmatory holdout evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from gateway_v7.runner import V7FunctionalProfile, run_functional_gate


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results_v7/strict_development"


def observer_projection(run: Path) -> list[tuple[object, ...]]:
    rows = [json.loads(line) for line in (run / "cloud_socket_boundary.jsonl").read_text().splitlines() if line]
    return [(row["direction"], row["session"], row["slot"], row["frame_bytes"], row["destination"]) for row in rows]


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite development results: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    count = 25
    pairs = {
        "DEV_TOOL_CLASS": (["FAST"] * count, ["SLOW"] * count),
        "DEV_RARE_TARGET": (["MEDIUM"] * count, ["MEDIUM"] * 24 + ["JITTERED"]),
    }
    rows = []
    for pair_id, (left, right) in pairs.items():
        profile = V7FunctionalProfile(name=f"V7-STRICT-DEV-{pair_id}", real_operations=count)
        left_path, right_path = OUTPUT / pair_id / "a", OUTPUT / pair_id / "b"
        left_result = run_functional_gate(ROOT, left_path, profile, provider_sequence=left,
                                          operation_prefix=f"{pair_id.lower()}-a")
        right_result = run_functional_gate(ROOT, right_path, profile, provider_sequence=right,
                                           operation_prefix=f"{pair_id.lower()}-b")
        left_projection, right_projection = observer_projection(left_path), observer_projection(right_path)
        rows.append({
            "pair_id": pair_id,
            "operations_per_arm": count,
            "arm_a_functional": left_result["functional_pass"],
            "arm_b_functional": right_result["functional_pass"],
            "endpoint_count_order_size_equal": left_projection == right_projection,
            "arm_a_results": left_result["unique_framework_results"],
            "arm_b_results": right_result["unique_framework_results"],
            "arm_a_dummy_heavy_ops": left_result["dummy_heavy_ops"],
            "arm_b_dummy_heavy_ops": right_result["dummy_heavy_ops"],
            "valid_pair": left_result["functional_pass"] and right_result["functional_pass"]
                and left_projection == right_projection,
        })
    with (ROOT / "STRICT_DEVELOPMENT_RESULTS_V7.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()

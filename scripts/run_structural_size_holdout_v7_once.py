from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from gateway_v7.runner import V7FunctionalProfile, run_functional_gate


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "STRUCTURAL_SIZE_HOLDOUT_V7_FREEZE.json"
FREEZE_HASH = ROOT / "STRUCTURAL_SIZE_HOLDOUT_V7_FREEZE_SHA256.txt"
OUTPUT = ROOT / "results_v7/structural_size_holdout"


def projection(path: Path) -> list[tuple[object, ...]]:
    rows = [json.loads(line) for line in (path / "cloud_socket_boundary.jsonl").read_text().splitlines() if line]
    return [(row["direction"], row["session"], row["slot"], row["frame_bytes"], row["destination"]) for row in rows]


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"one-shot holdout already exists: {OUTPUT}")
    if hashlib.sha256(FREEZE.read_bytes()).hexdigest() != FREEZE_HASH.read_text().strip():
        raise RuntimeError("structural holdout freeze hash mismatch")
    manifest = json.loads(FREEZE.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    public = manifest["public_profile"]
    profile = V7FunctionalProfile(**public)
    pair_rows, long_rows = [], []
    for pair in manifest["pairs"]:
        pair_id = pair["pair_id"]
        left_path, right_path = OUTPUT / pair_id / "a", OUTPUT / pair_id / "b"
        left = run_functional_gate(ROOT, left_path, profile, provider_sequence=pair["a"],
                                   operation_prefix=f"holdout-{pair_id.lower()}-a")
        right = run_functional_gate(ROOT, right_path, profile, provider_sequence=pair["b"],
                                    operation_prefix=f"holdout-{pair_id.lower()}-b")
        left_projection, right_projection = projection(left_path), projection(right_path)
        functional = bool(left["functional_pass"] and right["functional_pass"])
        exact = left_projection == right_projection
        pair_rows.append({
            "pair_id": pair_id,
            "secret": pair["secret"],
            "public_profile": profile.name,
            "operations_per_arm": profile.real_operations,
            "arm_a_functional": left["functional_pass"],
            "arm_b_functional": right["functional_pass"],
            "arm_a_results": left["unique_framework_results"],
            "arm_b_results": right["unique_framework_results"],
            "dummy_heavy_ops": left["dummy_heavy_ops"] + right["dummy_heavy_ops"],
            "endpoint_count_order_size_exact": exact,
            "valid_privacy_pair": functional and exact,
            "timing_evaluated": False,
        })
        for window in manifest["windows"]:
            # Two cloud events (request/response) are emitted per public slot. The
            # window is an operation-observation aggregation window; because the
            # complete structural projection is exact, every prefix is exact.
            prefix = min(len(left_projection), window * 2)
            long_rows.append({
                "pair_id": pair_id,
                "observation_window": window,
                "arm_a_functional": left["functional_pass"],
                "arm_b_functional": right["functional_pass"],
                "exact_projection_equal": left_projection[:prefix] == right_projection[:prefix],
                "classifier_run": False,
                "classifier_reason": "symbolic observer projections are exactly equal",
            })
    with (ROOT / "STRUCTURAL_SIZE_HOLDOUT_V7.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(pair_rows[0]))
        writer.writeheader(); writer.writerows(pair_rows)
    with (ROOT / "LONG_HORIZON_V7.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(long_rows[0]))
        writer.writeheader(); writer.writerows(long_rows)
    summary = {"pairs": len(pair_rows), "valid_pairs": sum(row["valid_privacy_pair"] for row in pair_rows),
               "all_exact": all(row["endpoint_count_order_size_exact"] for row in pair_rows),
               "timing_evaluated": False, "status": "EXECUTED_ONCE_NO_TUNING"}
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

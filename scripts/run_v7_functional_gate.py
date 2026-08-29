"""Run the V7 Linux functional gate; no privacy analysis is performed here."""

from __future__ import annotations

import argparse
import csv
import json
import platform
from pathlib import Path

from gateway_v7.runner import V7FunctionalProfile, run_functional_gate


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results_v7/functional_gate")
    parser.add_argument("--counts", default="1,10,50,100")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for count in [int(value) for value in args.counts.split(",")]:
        run_output = output / f"operations_{count}"
        result = run_functional_gate(
            ROOT,
            run_output,
            V7FunctionalProfile(name=f"V7-FUNCTIONAL-{count}", real_operations=count),
        )
        rows.append({
            "platform": platform.platform(),
            "operation_count": count,
            "admitted_operations": result["admitted_operations"],
            "unique_framework_results": result["unique_framework_results"],
            "missing_results": len(result["missing_operation_ids"]),
            "unexpected_results": len(result["unexpected_operation_ids"]),
            "duplicate_results_suppressed": result["duplicate_framework_results_suppressed"],
            "real_effects": result["real_effects"],
            "dummy_heavy_ops": result["dummy_heavy_ops"],
            "fixed_frames": result["fixed_frames"],
            "terminal_status": result["terminal_status"],
            "functional_pass": result["functional_pass"],
        })
    with (output / "functional_gate.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "functional_gate_summary.json").write_text(
        json.dumps({"all_pass": all(row["functional_pass"] for row in rows), "runs": rows}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()

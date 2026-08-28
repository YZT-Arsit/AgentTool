from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))]


def summary(population: str, metric: str, values: list[float], unit: str) -> dict[str, object]:
    return {
        "record_type": "DISTRIBUTION", "population": population, "metric": metric,
        "unit": unit, "count": len(values), "p50": percentile(values, .50),
        "p90": percentile(values, .90), "p95": percentile(values, .95),
        "p99": percentile(values, .99), "max": max(values),
        "fit_fraction": "", "overflow_fraction": "", "mean_cover_fraction": "",
        "bandwidth_bytes": "", "public_duration_ms": "", "notes": "",
    }


def main() -> None:
    fidelity = list(csv.DictReader((ROOT / "SEMANTIC_FIDELITY_V2_RESULTS.csv").open(encoding="utf-8")))
    projections = [json.loads(row["compiled_projection"]) for row in fidelity]

    def decoded(name: str) -> list[list[object]]:
        return [json.loads(str(item[name])) for item in projections]

    tool_arguments = decoded("tool_arguments")
    tool_results = decoded("tool_results")
    contexts = decoded("next_model_context")
    metrics: dict[str, tuple[list[float], str]] = {
        "model_calls": ([float(item["model_calls"]) for item in projections], "count"),
        "tool_calls": ([float(len(value)) for value in decoded("selected_tools")], "count"),
        "handoff_depth": ([float(len(value)) for value in decoded("handoff_targets")], "count"),
        "branch_count": ([float(len(value)) for value in decoded("branch_choices")], "count"),
        "control_updates": ([float(len(value)) for value in decoded("state_updates")], "count"),
        "tool_argument_bytes": ([float(len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()))
                                 for value in tool_arguments], "bytes"),
        "tool_result_bytes": ([float(len(json.dumps(value, separators=(",", ":")).encode()))
                               for value in tool_results], "bytes"),
        "next_model_context_bytes": ([float(max((len(str(item).encode()) for item in value), default=0))
                                      for value in contexts], "bytes"),
        "final_result_bytes": ([float(len(str(item["sanitized_final_result"]).encode()))
                                for item in projections], "bytes"),
        "effect_count": ([float(item["effect_count"]) for item in projections], "count"),
    }
    output = [summary("FROZEN_DYNAMIC_72", name, values, unit)
              for name, (values, unit) in metrics.items()]

    # Exact serialized capsule measurements from the three completed canonical
    # Linux workflow fixtures: read, effectful, and two-Agent handoff.
    for name, values, unit in (
        ("capsule_row_count", [4, 4, 1, 2], "rows_per_capsule"),
        ("encoded_capsule_bytes", [1024, 1024, 1024, 1024], "bytes"),
        ("tool_handles", [1, 1, 0, 0], "count"),
        ("handoff_targets", [0, 0, 1, 0], "count"),
    ):
        output.append(summary("CANONICAL_LINUX_WORKFLOW_CAPSULES", name,
                              [float(value) for value in values], unit))

    corpus = list(csv.DictReader((ROOT / "CORPUS_MANIFEST.csv").open(encoding="utf-8")))
    for field in ("agent_constructors", "tool_instances", "handoff_edges", "conditional_edges",
                  "loops", "fanout_fanin", "state_memory", "hitl_resume", "middleware"):
        output.append(summary("FROZEN_CORPUS_314_FILES", f"static_file_{field}",
                              [float(row[field]) for row in corpus], "instances_per_file"))

    lengths = [int(len(value)) for value in decoded("state_updates")]
    for horizon in (4, 6, 8):
        fits = [value <= horizon for value in lengths]
        cover = [max(0, horizon - min(value, horizon)) / horizon for value in lengths]
        output.append({
            "record_type": "PROFILE", "population": "FROZEN_DYNAMIC_72",
            "metric": f"GAMMA_H{horizon}_B1024_D40MS", "unit": "profile",
            "count": len(lengths), "p50": "", "p90": "", "p95": "", "p99": "", "max": "",
            "fit_fraction": sum(fits) / len(fits),
            "overflow_fraction": 1 - sum(fits) / len(fits),
            "mean_cover_fraction": statistics.mean(cover),
            "bandwidth_bytes": horizon * 2 * 1024,
            "public_duration_ms": horizon * 40,
            "notes": "control-update proxy; excludes PIR, startup, and heavy provider latency",
        })

    path = ROOT / "PROFILE_FEASIBILITY_RESULTS.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)


if __name__ == "__main__":
    main()

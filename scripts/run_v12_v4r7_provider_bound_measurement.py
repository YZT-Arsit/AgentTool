from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_full_scope.canonical import V11EvidenceProviders
from v11_full_scope.fixtures import tool_case


FREEZE = ROOT / "V12_V4R7_PROVIDER_BOUND_SELECTION_FREEZE.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nearest_rank(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def summary_ms(values: list[int]) -> dict[str, float]:
    if not values:
        raise RuntimeError("cannot summarize an empty measurement")
    return {
        name: value / 1_000_000
        for name, value in {
            "p50": nearest_rank(values, 0.5),
            "p90": nearest_rank(values, 0.9),
            "p95": nearest_rank(values, 0.95),
            "p99": nearest_rank(values, 0.99),
            "p99_9": nearest_rank(values, 0.999),
            "max": max(values),
        }.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--go-root", type=Path, default=ROOT / "common_action_gateway_v2")
    args = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    attempts = list(freeze["attempts"])
    if len(attempts) != 10_000 or len({row["operation_id"] for row in attempts}) != 10_000:
        raise RuntimeError("provider bound measurement freeze is malformed")
    args.output.mkdir(parents=True, exist_ok=False)
    raw_output = args.output / "provider_measurement_raw.json"
    provider_evidence = args.output / "provider_private_evidence.json"
    base = tool_case("DEV-V4R7-BMEASURE-TEMPLATE", "FRAMEWORK_NEUTRAL")
    cases = {
        row["operation_id"]: replace(
            base,
            case_id=row["identity"],
            operation_id=row["operation_id"],
        )
        for row in attempts
    }
    with V11EvidenceProviders(cases, provider_evidence) as providers:
        environment = dict(os.environ)
        environment.update(
            {
                "V12_PROVIDER_MEASUREMENT_MANIFEST": str(FREEZE),
                "V12_PROVIDER_MEASUREMENT_OUTPUT": str(raw_output),
                "V12_PROVIDER_MEASUREMENT_ENDPOINT": providers.endpoints["route-tool-read"],
                "V12_PROVIDER_MEASUREMENT_TIMEOUT_MS": str(
                    freeze["measurement_only_timeout_ms"]
                ),
            }
        )
        completed = subprocess.run(
            [
                "go",
                "test",
                "-tags",
                "v12_provider_measurement",
                "./canonicalv9",
                "-run",
                "^TestV12ProviderBoundMeasurement$",
                "-count=1",
            ],
            cwd=args.go_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    (args.output / "go_test_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (args.output / "go_test_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0 or not raw_output.exists():
        raise RuntimeError(f"provider measurement failed with rc={completed.returncode}")
    raw = json.loads(raw_output.read_text(encoding="utf-8"))["results"]
    private = json.loads(provider_evidence.read_text(encoding="utf-8"))
    if len(raw) != 10_000 or len(private) != 10_000:
        raise RuntimeError("provider measurement inventory is incomplete")
    by_operation = {row["operation_id"]: row for row in private}
    if len(by_operation) != 10_000:
        raise RuntimeError("provider private evidence contains duplicate operation IDs")
    end_to_end_ns = [int(row["diagnostic"]["elapsed_ns"]) for row in raw]
    logical_ns = []
    for row in raw:
        evidence = by_operation[row["operation_id"]]
        logical_ns.append(
            int(evidence["handler_logical_completion_monotonic_ns"])
            - int(evidence["handler_start_monotonic_ns"])
        )
    end_to_end = summary_ms(end_to_end_ns)
    logical = summary_ms(logical_ns)
    required = math.ceil(end_to_end["max"] + 50)
    selected = next(
        (candidate for candidate in freeze["candidate_bounds_ms"] if candidate >= required),
        None,
    )
    summary = {
        "schema": "AgentTool.V12V4R7ProviderBoundSelectionMeasurement/1",
        "freeze_sha256": sha256(FREEZE),
        "measurement_only_timeout_ms": freeze["measurement_only_timeout_ms"],
        "sessions": freeze["measurement_sessions"],
        "attempts_per_session": freeze["attempts_per_session"],
        "attempts": len(raw),
        "protected_workload_labels": 0,
        "all_provider_status_ok": all(
            row["diagnostic"]["class"] == "PROVIDER_OK" for row in raw
        ),
        "provider_end_to_end_ms": end_to_end,
        "provider_logical_work_ms": logical,
        "required_bound_ms": required,
        "candidate_bounds_ms": freeze["candidate_bounds_ms"],
        "selected_bound_ms": selected,
        "selection_status": "PASS" if selected is not None else "FAIL",
        "raw_output_sha256": sha256(raw_output),
        "private_evidence_sha256": sha256(provider_evidence),
    }
    (args.output / "PROVIDER_BOUND_SELECTION_RESULT.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if selected is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())

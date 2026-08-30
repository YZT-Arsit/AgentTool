from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def functional(summary: dict[str, Any]) -> bool:
    """Apply the pre-existing V11.3 workflow-specific causal rule.

    DYNAMIC_SEQUENCE claims online causality and therefore requires its causal
    proof.  PARALLEL_ACTIONS deliberately does not make that claim; requiring
    sequential causality there is a category error, not a functional check.
    """

    causal_required = summary.get("workflow") == "DYNAMIC_SEQUENCE"
    return all(
        (
            summary.get("trace_gate", {}).get("passed") is True,
            summary.get("semantic_equal") is True,
            summary.get("dynamic_pir") is True,
            not summary.get("error"),
            summary.get("causal_proof", {}).get("passed") is True
            if causal_required
            else True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()

    original_result_path = root / "result.json"
    original_structural_path = root / "structural_regression.csv"
    original = load(original_result_path)
    if original.get("status") != "FAIL":
        raise RuntimeError("analysis correction is only defined for the retained false-negative run")
    if original.get("selected_v12_cases_executed") != 0:
        raise RuntimeError("selected V12 execution is forbidden")

    original_rows = list(csv.DictReader(original_structural_path.open(encoding="utf-8")))
    if len(original_rows) != 12:
        raise RuntimeError("unexpected structural-regression denominator")

    corrected_rows: list[dict[str, Any]] = []
    corrected_pairs: list[str] = []
    for row in original_rows:
        pair = row["pair"]
        pair_root = root / "regression_raw" / "structural" / pair.lower()
        arm_a = load(pair_root / "A" / "v11_3_development_summary.json")
        arm_b = load(pair_root / "B" / "v11_3_development_summary.json")
        arm_a_functional = functional(arm_a)
        arm_b_functional = functional(arm_b)
        structural_equal = arm_a.get("strict_structural_projection") == arm_b.get(
            "strict_structural_projection"
        )
        size_equal = arm_a.get("strict_size_projection") == arm_b.get(
            "strict_size_projection"
        )
        passed = all((arm_a_functional, arm_b_functional, structural_equal, size_equal))
        corrected_rows.append(
            {
                "pair": pair,
                "arm_a_functional": arm_a_functional,
                "arm_b_functional": arm_b_functional,
                "structural_equal": structural_equal,
                "size_equal": size_equal,
                "passed": passed,
                "arm_a_workflow": arm_a.get("workflow"),
                "arm_b_workflow": arm_b.get("workflow"),
                "causal_rule": "REQUIRE_ONLY_FOR_DYNAMIC_SEQUENCE",
            }
        )
        if str(row["passed"]).lower() != str(passed).lower():
            corrected_pairs.append(pair)

    if corrected_pairs != ["CAUSAL_DEPTH"]:
        raise RuntimeError(f"unexpected analysis correction scope: {corrected_pairs}")
    causal_b = load(
        root
        / "regression_raw"
        / "structural"
        / "causal_depth"
        / "B"
        / "v11_3_development_summary.json"
    )
    if causal_b.get("workflow") != "PARALLEL_ACTIONS":
        raise RuntimeError("the corrected arm is not the predeclared parallel control")
    if causal_b.get("trace_gate", {}).get("passed") is not True:
        raise RuntimeError("the corrected arm has a genuine functional failure")

    corrected_csv = root / "structural_regression_analysis_corrected.csv"
    with corrected_csv.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(corrected_rows[0]))
        writer.writeheader()
        writer.writerows(corrected_rows)

    corrected = dict(original)
    corrected["schema"] = "AgentTool.V12ProfileRequalificationAnalysisCorrection/1"
    corrected["original_result_status"] = original["status"]
    corrected["original_result_retained"] = True
    corrected["execution_rerun"] = False
    corrected["corrected_pairs"] = corrected_pairs
    corrected["analysis_rule"] = (
        "causal proof is required for DYNAMIC_SEQUENCE and not for the "
        "predeclared PARALLEL_ACTIONS control"
    )
    corrected["gates"] = dict(original["gates"])
    corrected["gates"]["structural_regression_at_least_12"] = all(
        row["passed"] for row in corrected_rows
    )
    corrected["status"] = "PASS" if all(corrected["gates"].values()) else "FAIL"
    write_json(root / "result_analysis_corrected.json", corrected)

    (root / "PROFILE_REQUALIFICATION_ANALYSIS_CORRECTION.md").write_text(
        "# V12 profile requalification analysis correction\n\n"
        "The original one-shot execution and its `result.json` are retained unchanged. "
        "Its sole failed gate was a false-negative analyzer rule: the predeclared "
        "CAUSAL_DEPTH B arm is `PARALLEL_ACTIONS`, while the V12 analyzer accidentally "
        "required the online sequential-causality proof from every workflow. The prior "
        "V11.3 rule requires that proof only for `DYNAMIC_SEQUENCE`. Reapplying that "
        "existing rule to the immutable raw summaries changes only CAUSAL_DEPTH B's "
        "functional classification. No execution was retried; the arm was COMPLETE, "
        "its trace gate passed, all ten expected operations/results were present, the "
        "paired structural and size projections were equal, and all safety counters "
        "were zero.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": corrected["status"], "execution_rerun": False}))


if __name__ == "__main__":
    main()

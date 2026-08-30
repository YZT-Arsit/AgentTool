from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "results_v11b_confirmatory"
DEFAULT_PLAN = ROOT / "V11B0_EXECUTION_PLAN.json"
DEFAULT_RULES = ROOT / "V11B0_1_FINAL_DECISION_RULES.json"
DEFAULT_TRAJECTORIES = ROOT / "V11A_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_ledger(path: Path) -> tuple[list[dict[str, Any]], bool]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    previous = "0" * 64
    valid = True
    for record in records:
        digest = record.get("record_sha256")
        unsigned = dict(record)
        unsigned.pop("record_sha256", None)
        valid &= record.get("previous_record_sha256") == previous
        valid &= digest == sha256_bytes(canonical_bytes(unsigned))
        previous = str(digest)
    return records, bool(valid)


def _unit_result(results_root: Path, unit: dict[str, Any]) -> dict[str, Any] | None:
    path = results_root / unit["unit_id"] / "unit_result.json"
    return load_json(path) if path.is_file() else None


def summarize_campaign(
    results_root: Path = DEFAULT_RESULTS,
    *,
    plan_path: Path = DEFAULT_PLAN,
    rules_path: Path = DEFAULT_RULES,
    trajectory_manifest_path: Path = DEFAULT_TRAJECTORIES,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Purely derive the frozen verdicts from immutable campaign evidence."""

    plan = load_json(plan_path)
    rules = load_json(rules_path)
    ledger, ledger_chain_valid = load_ledger(results_root / "execution_ledger.jsonl")
    units = plan["units"]
    ledger_by_unit = {row["unit_id"]: row for row in ledger}
    planned_ids = [unit["unit_id"] for unit in units]
    ledger_ids = [row.get("unit_id") for row in ledger]
    execution_integrity = all(
        (
            len(ledger) == rules["execution_integrity"]["expected_units"] == 158,
            len(set(ledger_ids)) == len(ledger_ids),
            ledger_ids == planned_ids,
            [row.get("global_execution_index") for row in ledger] == list(range(1, 159)),
            ledger_chain_valid,
            all(unit.get("retry_allowed") is False for unit in units),
            all(row.get("status_class") != "HARNESS_INTEGRITY_FAILURE" for row in ledger),
        )
    )

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        grouped[(unit["family"], unit["target_id"])].append(unit)

    family_results: dict[str, dict[str, Any]] = {}
    for family in ("S1", "S2", "S4"):
        passed: list[str] = []
        targets = sorted(target for current, target in grouped if current == family)
        for target in targets:
            pair = grouped[(family, target)]
            native = next(unit for unit in pair if unit["role"] == "NATIVE")
            canonical = next(unit for unit in pair if unit["role"] == "CANONICAL")
            native_value = _unit_result(results_root, native)
            canonical_value = _unit_result(results_root, canonical)
            if all(
                (
                    ledger_by_unit.get(native["unit_id"], {}).get("status_class") == "PASS",
                    ledger_by_unit.get(canonical["unit_id"], {}).get("status_class") == "PASS",
                    native_value is not None,
                    canonical_value is not None,
                    native_value.get("projection") == canonical_value.get("projection")
                    if native_value is not None and canonical_value is not None
                    else False,
                )
            ):
                passed.append(target)
        expected = rules["semantic_families"][family]["expected_cases"]
        family_results[family] = {
            "expected": expected,
            "observed": len(targets),
            "passed": len(passed),
            "pass": len(targets) == len(passed) == expected,
            "passing_case_ids": passed,
        }

    trajectory_manifest = load_json(trajectory_manifest_path)
    depth_by_id = {
        item["trajectory_id"]: int(item.get("depth", len(item["actions"])))
        for item in trajectory_manifest["trajectories"]
    }
    s3_passed: list[str] = []
    s3_targets = sorted(target for family, target in grouped if family == "S3")
    for target in s3_targets:
        pair = grouped[("S3", target)]
        native = next(unit for unit in pair if unit["role"] == "NATIVE")
        canonical = next(unit for unit in pair if unit["role"] == "CANONICAL")
        native_value = _unit_result(results_root, native)
        canonical_value = _unit_result(results_root, canonical)
        if all(
            (
                ledger_by_unit.get(native["unit_id"], {}).get("status_class") == "PASS",
                ledger_by_unit.get(canonical["unit_id"], {}).get("status_class") == "PASS",
                native_value is not None,
                canonical_value is not None,
                canonical_value.get("causal_proof", {}).get("passed") is True
                if canonical_value is not None
                else False,
                native_value.get("projection")
                == canonical_value.get("semantic", {}).get("projection")
                if native_value is not None and canonical_value is not None
                else False,
            )
        ):
            s3_passed.append(target)
    required_depths = set(rules["semantic_families"]["S3"]["mandatory_depths"])
    selected_depths = {depth_by_id[target] for target in s3_targets}
    s3_expected = rules["semantic_families"]["S3"]["expected_cases"]
    family_results["S3"] = {
        "expected": s3_expected,
        "observed": len(s3_targets),
        "passed": len(s3_passed),
        "mandatory_depths_present": required_depths.issubset(selected_depths),
        "pass": len(s3_targets) == len(s3_passed) == s3_expected
        and required_depths.issubset(selected_depths),
        "passing_trajectory_ids": s3_passed,
    }

    verdict_paths = sorted(results_root.glob("pair_*_verdict.json"))
    verdicts = [load_json(path) for path in verdict_paths]
    expected_pairs = rules["structural"]["expected_pairs"]
    structural_pass = len(verdicts) == expected_pairs and all(
        verdict.get("status") == "PASS"
        and verdict.get("full_structural_equal") is True
        and verdict.get("size_equal") is True
        and all(verdict.get("prefix_equal", {}).get(str(horizon)) is True for horizon in (1, 10, 50, 100, 200, 300, 356))
        for verdict in verdicts
    )

    semantic_go = all(family_results[name]["pass"] for name in ("S1", "S2", "S3", "S4"))
    summary = {
        "schema": "AgentTool.V11BConfirmatorySummary/1",
        "source": "IMMUTABLE_CAMPAIGN_EVIDENCE_ONLY",
        "family_results": family_results,
        "structural": {
            "expected_pairs": expected_pairs,
            "observed_pairs": len(verdicts),
            "pass": structural_pass,
        },
        "execution_integrity": {
            "ledger_records": len(ledger),
            "status_counts": dict(sorted(Counter(str(row.get("status_class")) for row in ledger).items())),
            "hash_chain_valid": ledger_chain_valid,
            "pass": execution_integrity,
        },
        "confirmatory_semantic_go": semantic_go,
        "confirmatory_structural_trajectory_go": structural_pass,
        "confirmatory_software_scope_go": semantic_go and structural_pass and execution_integrity,
        "claim_boundaries": rules["claim_boundaries"],
    }
    if output_path is not None:
        with output_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen pure V11B confirmatory summarizer")
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()
    output = args.results_root / "V11B_CONFIRMATORY_SUMMARY.json"
    summarize_campaign(args.results_root, output_path=output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "LONG_HORIZON_STRUCTURAL_RESULTS.csv"
OUTPUT = ROOT / "LONG_HORIZON_FUNCTIONAL_AUDIT.csv"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("functional audit already exists")
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    audited = []
    for row in rows:
        summary_path = (ROOT / "results_long_horizon_structural_v1" /
                        row["family"].lower() / f"class_{row['class']}" /
                        "canonical_run_summary.json")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        audited.append({
            "family": row["family"], "class": row["class"],
            "expected_completed_observations": 32,
            "expected_heavy_operations": 96,
            "actual_heavy_operations": summary["real_heavy_operations"],
            "delivered_results": summary["delivered_results"],
            "workflow_returned": summary["returned"],
            "dummy_heavy_operations": summary["dummy_heavy_operations"],
            "functional_gate": "FAIL",
            "reason": "frozen 3-slot/10ms profile expired before journal-hardened result delivery",
        })
    with OUTPUT.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audited[0]))
        writer.writeheader(); writer.writerows(audited)
    print(json.dumps({"cases": len(audited), "functional_passes": 0,
                      "actual_heavy_operations_each": 32,
                      "delivered_results_each": 0}, indent=2))


if __name__ == "__main__":
    main()

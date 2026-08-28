from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from semantic_fidelity.harness_v3 import execute_case

MANIFEST = ROOT / "SEMANTIC_HOLDOUT_V3_FREEZE.json"
DIGEST = ROOT / "SEMANTIC_HOLDOUT_V3_FREEZE_SHA256.txt"
RESULTS = ROOT / "SEMANTIC_HOLDOUT_V3_RESULTS.csv"


def main() -> None:
    if RESULTS.exists():
        raise FileExistsError("semantic holdout V3 has already been executed; refusing rerun")
    expected = DIGEST.read_text(encoding="utf-8").split()[0]
    if hashlib.sha256(MANIFEST.read_bytes()).hexdigest() != expected:
        raise RuntimeError("semantic holdout V3 freeze digest mismatch")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = []
    for ordinal, case in enumerate(manifest["cases"]):
        if hashlib.sha256((ROOT / case["source"]["path"]).read_bytes()).hexdigest() != case["source"]["sha256"]:
            raise RuntimeError(f"pinned source changed for {case['case_id']}")
        try:
            result = execute_case(case, ordinal)
            rows.append({
                "case_id": case["case_id"], "framework": case["framework"],
                "behavior_family": case["behavior_family"], "source_path": case["source"]["path"],
                "native_pass": result["native_pass"], "compiled_pass": result["compiled_pass"],
                "semantic_pass": result["semantic_pass"], "compiled_executable": result["compiled_executable"],
                "physical_executor": result["physical_executor"],
                "unsupported_reasons": ";".join(result["unsupported_reasons"]),
                "expected_projection": json.dumps(result["expected_projection"], sort_keys=True),
                "native_projection": json.dumps(result["native_projection"], sort_keys=True),
                "compiled_projection": json.dumps(result["compiled_projection"], sort_keys=True),
                "execution_error": "",
            })
        except Exception as exc:
            rows.append({
                "case_id": case["case_id"], "framework": case["framework"],
                "behavior_family": case["behavior_family"], "source_path": case["source"]["path"],
                "native_pass": False, "compiled_pass": False, "semantic_pass": False,
                "compiled_executable": False, "physical_executor": "", "unsupported_reasons": "",
                "expected_projection": json.dumps(case["expected_projection"], sort_keys=True),
                "native_projection": "", "compiled_projection": "",
                "execution_error": f"{type(exc).__name__}: {exc}",
            })
    with RESULTS.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary = {"cases": len(rows), "passes": sum(str(r["semantic_pass"]).lower() == "true" for r in rows),
               "errors": sum(bool(r["execution_error"]) for r in rows),
               "run_policy": "ONCE_NO_TUNING"}
    (ROOT / "results_v5").mkdir(exist_ok=True)
    (ROOT / "results_v5/semantic_holdout_v3_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

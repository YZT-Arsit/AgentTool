from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(value, encoding="utf-8")


def main() -> None:
    tree = json.loads((ROOT / "V11B_RESULT_TREE_MANIFEST.json").read_text(encoding="utf-8"))
    audit = {
        "schema": "AgentTool.V11B.AbortedConfirmatoryAudit/1",
        "classification": "STARTED_INCOMPLETE_NO_RETRY",
        "v11b_holdout_consumed": True,
        "v11b_rerun_allowed": False,
        "v11b_confirmatory_result_available": False,
        "selected_units_planned": 158,
        "ledger_records": 157,
        "selected_unit_158_entered_without_final_ledger_record": True,
        "status_class_counts": {"PASS": 65, "CANONICAL_FUNCTIONAL_FAIL": 92},
        "final_ledger_record_sha256": "550ba235aef5186c5a8cc5d5cfa1265c380aa39d69c32baf0642d77894c33158e",
        "execution_ledger_sha256": "1e78428ba3f614cfe087e83c9d943f17563130cf2018be8c9ee7ef06b279663db",
        "primary_common_failure": "FileNotFoundError: online SimplePIR requires Go and gcc",
        "terminal_campaign_failure": "OSError: [Errno 24] Too many open files",
        "privacy_failure_inferred": False,
        "missing_artifacts_not_synthesized": [
            "158th ledger record",
            "V11B_CONFIRMATORY_SUMMARY.json",
            "campaign_completion.json",
            "missing pair verdicts",
        ],
        "result_tree_manifest_file_sha256": sha256(ROOT / "V11B_RESULT_TREE_MANIFEST.json"),
        "result_tree_aggregate_sha256": tree["aggregate_canonical_manifest_sha256"],
        "result_tree_files": tree["file_count"],
        "result_tree_bytes": tree["total_bytes"],
    }
    write_json(ROOT / "V11B_ABORTED_CONFIRMATORY_AUDIT.json", audit)
    write_text(
        ROOT / "V11B_ABORTED_CONFIRMATORY_AUDIT.md",
        """# V11B Aborted Confirmatory Campaign Audit

V11B is permanently classified **STARTED / INCOMPLETE / NO RETRY**. Its holdout
was consumed, but it produced no confirmatory privacy verdict. The 157-record
append-only ledger contains 65 native `PASS` records and 92
`CANONICAL_FUNCTIONAL_FAIL` records. Unit 158 entered execution but no final
ledger record was committed.

The recurring canonical failure was `FileNotFoundError: online SimplePIR
requires Go and gcc`; the terminal failure was `OSError: [Errno 24] Too many
open files`. These are harness/runtime failures and are not counted as privacy
failures. No missing record, summary, completion anchor, or pair verdict has
been synthesized, and no selected unit has been rerun.

The separately frozen recursive result-tree manifest binds every existing byte
of the remote result tree. V11B may be cited only as an aborted harness run.

- `V11B_HOLDOUT_CONSUMED = YES`
- `V11B_RERUN_ALLOWED = NO`
- `V11B_CONFIRMATORY_RESULT_AVAILABLE = NO`
""",
    )
    provenance = {
        "schema": "AgentTool.V11B.DriverProvenanceAudit/1",
        "historical_source_commit": "5294978fdf1a8cfd35e04b2e1e9b08158fc435e3",
        "frozen_execution_plan_sha256": sha256(ROOT / "V11B0_EXECUTION_PLAN.json"),
        "driver_sha256": sha256(ROOT / "scripts" / "run_v11b_confirmatory.py"),
        "summarizer_sha256": sha256(ROOT / "scripts" / "summarize_v11b_confirmatory.py"),
        "artifact_manifest_sha256": sha256(ROOT / "V11B_EXECUTION_ARTIFACT_MANIFEST.json"),
        "canonical_runner_sha256": "14eb0488813425a99e49ac74741777fb5022a04ada6577a5b00bb5d2ef119877",
        "simplepir_bridge_sha256": "2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b",
        "ledger_record_count": 157,
        "planned_unit_count": 158,
        "rerun_performed": False,
        "result_tree_mutated_by_v12": False,
    }
    write_json(ROOT / "V11B_DRIVER_PROVENANCE_AUDIT.json", provenance)


if __name__ == "__main__":
    main()

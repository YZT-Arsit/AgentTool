from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "V12_DUPLEX_V4R6_RELIABILITY_CONTINUATION_EVIDENCE"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    reliability = json.loads(
        (EVIDENCE / "SYNTHETIC_RELIABILITY_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    functional = json.loads(
        (EVIDENCE / "FUNCTIONAL_REQUALIFICATION_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    freeze = json.loads(
        (ROOT / "V12_DUPLEX_V4R6_RELIABILITY_CONTINUATION_FREEZE.json").read_text(
            encoding="utf-8"
        )
    )
    records = reliability["records"]
    assert reliability["planned_sessions"] == 200
    assert reliability["executed_sessions"] == 200
    assert reliability["passed_sessions"] == 200
    assert reliability["failed_sessions"] == 0
    assert reliability["retries"] == 0
    assert reliability["status"] == "PASS"
    assert [row["identity"] for row in records] == freeze[
        "synthetic_reliability_identities"
    ]
    assert all(row["pass"] and all(row["checks"].values()) for row in records)
    assert functional["planned_units"] == 16
    assert functional["executed_units"] == 14
    assert functional["passed_units"] == 13
    assert functional["failed_units"] == 1
    assert functional["retries"] == 0
    assert functional["status"] == "FAIL"
    failed = [row for row in functional["units"] if not row["pass"]]
    assert len(failed) == 1
    failed_unit = failed[0]
    failed_checks = [
        name
        for section in ("common_checks", "functional_checks")
        for name, passed in failed_unit[section].items()
        if not passed
    ]
    assert failed_checks == ["level_a_semantics"]
    archive_files = (
        "synthetic_reliability_records.tar.gz",
        "p10_functional_requalification_records.tar.gz",
    )
    archive_hashes = {name: sha256(EVIDENCE / name) for name in archive_files}
    persistence = {
        "schema": "AgentTool.V12ExecutionInfrastructurePersistenceGate/1",
        "mechanism": "nohup worker detached from interactive SSH control shell",
        "harmless_worker_pid": 70451,
        "started_marker": "gate-5157e217",
        "started_mtime": "2026-09-02 18:43:52.677477016 +0800",
        "control_ssh_disconnected": True,
        "reconnected_with_new_ssh_session": True,
        "completed_marker": "gate-5157e217",
        "completed_mtime": "2026-09-02 18:44:12.681554139 +0800",
        "formal_worker_pid": 70838,
        "formal_worker_ppid_after_reconnect": 1,
        "formal_worker_exit_code": 0,
        "status": "PASS",
    }
    write_json(EVIDENCE / "INFRASTRUCTURE_PERSISTENCE_GATE.json", persistence)
    integrity = {
        "schema": "AgentTool.V12DuplexV4R6ExecutionIntegrity/1",
        "execution_source_commit": "5157e21756d0ada9c6c7c8052d142e5bfe0d0e34",
        "base_closure": "ff17b72330dec8ae2ba1d9746e5d511d8fb7a84e",
        "runtime_commit": "bc3ba150e21873817c4ff2372bd80a29b968257c",
        "runtime_commit_is_ancestor": True,
        "protected_runtime_diff_from_runtime_commit": [],
        "profile_id": reliability["profile_id"],
        "profile_rounds": 506,
        "pir_opportunities": 100,
        "response_public_lag_ms": 30,
        "response_preparation_lead_ms": 20,
        "go_runner_sha256": "ec2befb4e83eac13b70dfef971362a2c758b40f5491e0364e3ddfc4f5149a548",
        "simplepir_runner_sha256": "743684a35afcee942ff76810a091925ce9ca8eb21e33519c3748c694ef1c6f8c",
        "freeze_sha256": sha256(
            ROOT / "V12_DUPLEX_V4R6_RELIABILITY_CONTINUATION_FREEZE.json"
        ),
        "reliability_runner_sha256": sha256(
            ROOT / "scripts/run_v12_duplex_response_reliability.py"
        ),
        "functional_runner_sha256": sha256(
            ROOT / "scripts/run_v12_duplex_v4r6_functional_continuation.py"
        ),
        "module_probe_paths": [
            "/root/autodl-tmp/v12_v4r6_reliability_5157e217/v12_timing/profile.py",
            "/root/autodl-tmp/v12_v4r6_reliability_5157e217/v11_online/session.py",
            "/root/autodl-tmp/v12_v4r6_reliability_5157e217/v11_online/frameworks.py",
        ],
        "status": "PASS",
    }
    write_json(EVIDENCE / "EXECUTION_INTEGRITY.json", integrity)
    oa_units = [
        row for row in functional["units"] if row["framework"] == "OpenAI Agents SDK"
    ]
    ms_units = [
        row
        for row in functional["units"]
        if row["framework"] == "Microsoft Agent Framework"
    ]
    closure = {
        "schema": "AgentTool.V12DuplexV4R6ReliabilityContinuationClosure/1",
        "base_closure": freeze["base_closure"],
        "runtime_commit": freeze["runtime_commit"],
        "v4r6_runtime_changed": False,
        "infrastructure_persistence_gate": "PASS",
        "historical_synthetic_support": "28 / 28 PASS",
        "new_synthetic_planned": 200,
        "new_synthetic_executed": reliability["executed_sessions"],
        "new_synthetic_retries": reliability["retries"],
        "new_synthetic_complete_pass": f'{reliability["passed_sessions"]} / 200',
        "missing_relay_slots": 0,
        "deadline_misses": sum(row["deadline_miss_count"] for row in records),
        "max_release_slip_ns": max(
            row["maximum_release_slip_ns"] for row in records
        ),
        "v4r6_synthetic_reliability": "PASS",
        "p10_functional_requalification": {
            "status": "FAIL",
            "planned_units": functional["planned_units"],
            "executed_units": functional["executed_units"],
            "passed_units": functional["passed_units"],
            "failed_units": functional["failed_units"],
            "retries": functional["retries"],
            "openai": f'{sum(row["pass"] for row in oa_units)} / {len(oa_units)} PASS',
            "microsoft": f'{sum(row["pass"] for row in ms_units)} / {len(ms_units)} executed PASS',
            "failed_identity": failed_unit["identity"],
            "failed_workload": failed_unit["workload"],
            "failed_framework": failed_unit["framework"],
            "failed_checks": failed_checks,
            "not_run_identities": freeze["functional_identities"][
                functional["executed_units"] :
            ],
        },
        "p10_v4r6_functional": "FAIL",
        "protected_classifier_runs": 0,
        "protected_auc": 0,
        "p20": "NOT_RUN",
        "p25": "NOT_RUN",
        "ready_for_duplex_repair_smoke": "NO",
        "timing_privacy": "INCONCLUSIVE",
        "timing_go": "NO",
        "archive_sha256": archive_hashes,
        "raw_records_preserved": True,
    }
    write_json(EVIDENCE / "CLOSURE.json", closure)
    md = f"""# V12 Duplex V4R6 Reliability Continuation Closure

The infrastructure persistence gate passed. A harmless `nohup` worker completed after its controlling SSH shell disconnected, and the formal reliability worker was subsequently observed with PPID 1 from a new SSH connection.

The fresh synthetic public-path qualification passed **200/200** with zero retries, zero missing Relay slots, zero deadline misses, and maximum response-release slip `{closure['max_release_slip_ns']}` ns. The historical 28/28 remains separate supporting evidence and is not included in this denominator.

P10 functional requalification stopped at the first failure, as frozen. It executed 14/16 units: 13 passed and one failed. OpenAI passed 8/8. Microsoft passed its first 5 units; `DEV-DTVR-V4R6-P10-CONT-MS-CACHE_REUSE_30-002` failed only the `level_a_semantics` functional check while every recorded common-integrity check and all other recorded functional checks passed. It was not retried; the final two identities were not run.

Therefore `V4R6_SYNTHETIC_RELIABILITY = PASS`, `P10_V4R6_FUNCTIONAL = FAIL`, and `READY_FOR_DUPLEX_REPAIR_SMOKE = NO`. No protected classifier, AUC, P20, P25, or smoke execution occurred.
"""
    (EVIDENCE / "CLOSURE.md").write_text(md, encoding="utf-8")
    evidence_hashes = [
        f"{sha256(path)}  {path.name}"
        for path in sorted(EVIDENCE.iterdir())
        if path.is_file() and path.name != "EVIDENCE_SHA256SUMS.txt"
    ]
    (EVIDENCE / "EVIDENCE_SHA256SUMS.txt").write_text(
        "\n".join(evidence_hashes) + "\n", encoding="utf-8"
    )
    print(json.dumps(closure, indent=2))


if __name__ == "__main__":
    main()

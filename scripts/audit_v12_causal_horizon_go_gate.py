from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite Go audit: {args.output}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    gate = json.loads(args.gate.read_text(encoding="utf-8"))
    events = [json.loads(line) for line in args.log.read_text(encoding="utf-8").splitlines()]
    passed = {
        (str(event.get("Package")), str(event.get("Test")))
        for event in events
        if event.get("Action") == "pass" and event.get("Test") and "/" not in str(event.get("Test"))
    }
    failed = [
        {"package": event.get("Package"), "test": event.get("Test")}
        for event in events
        if event.get("Action") == "fail" and event.get("Test") and "/" not in str(event.get("Test"))
    ]
    expected = int(manifest["test_count"])
    valid = len(passed) == expected and not failed and all(code == 0 for code in gate["exit_codes"])
    payload = {
        "schema": "AgentTool.V12CausalHorizonGoGateTopLevelAudit/1",
        "manifest_sha256": sha(args.manifest),
        "raw_gate_sha256": sha(args.gate),
        "raw_log_sha256": sha(args.log),
        "raw_gate_status_preserved": gate["status"],
        "raw_gate_counting_defect": "Go subtests containing '/' were counted in addition to their frozen top-level parent nodes",
        "expected_top_level_tests": expected,
        "passed_top_level_tests": len(passed),
        "failed_top_level_tests": failed,
        "package_exit_codes": gate["exit_codes"],
        "audited_status": "PASS" if valid else "FAIL",
        "no_test_reexecution": True,
        "timing_attack_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_json_tests(
    *,
    go: Path,
    cwd: Path,
    env: dict[str, str],
    package: str,
    tests: list[str],
) -> tuple[list[str], int, str]:
    pattern = "^(?:" + "|".join(re.escape(test) for test in tests) + ")$"
    command = [str(go), "test", "-count=1", "-timeout=10m", "-json", "-run", pattern, package]
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return command, result.returncode, result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--gateway-root", type=Path, required=True)
    parser.add_argument("--bridge-root", type=Path, required=True)
    parser.add_argument("--gopath", type=Path, required=True)
    parser.add_argument("--go", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite Go gate: {output}")
    output.mkdir(parents=True)
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    package_paths = {
        "common-action-gateway-v2": ".",
        "common-action-gateway-v2/canonicalv9": "./canonicalv9",
        "common-action-gateway-v2/v7": "./v7",
        "common-action-gateway-v2/v7ohttp": "./v7ohttp",
        "common-action-gateway-v2/v8": "./v8",
        "common-action-gateway-v2/v9ohttp": "./v9ohttp",
    }
    gateway_env = os.environ.copy()
    gateway_env.update(
        {
            "GO111MODULE": "off",
            "GOPATH": str(args.gopath.resolve()),
            "GOPROXY": "off",
            "GONOSUMDB": "*",
            "CGO_ENABLED": "1",
        }
    )
    bridge_env = os.environ.copy()
    bridge_env.update({"CGO_ENABLED": "1"})
    all_events: list[dict[str, object]] = []
    commands: list[list[str]] = []
    exit_codes: list[int] = []
    logs: list[str] = []
    started = time.time_ns()
    for package, tests in manifest["packages"].items():
        command, exit_code, stdout = run_json_tests(
            go=args.go.resolve(),
            cwd=args.gateway_root.resolve(),
            env=gateway_env,
            package=package_paths[package],
            tests=tests,
        )
        commands.append(command)
        exit_codes.append(exit_code)
        logs.append(stdout)
        for line in stdout.splitlines():
            try:
                all_events.append(json.loads(line))
            except json.JSONDecodeError:
                all_events.append({"Action": "unparsed", "Output": line})
        if exit_code != 0:
            break
    if all(code == 0 for code in exit_codes):
        command, exit_code, stdout = run_json_tests(
            go=args.go.resolve(),
            cwd=args.bridge_root.resolve(),
            env=bridge_env,
            package=".",
            tests=manifest["simplepir_bridge_tests"],
        )
        commands.append(command)
        exit_codes.append(exit_code)
        logs.append(stdout)
        for line in stdout.splitlines():
            try:
                all_events.append(json.loads(line))
            except json.JSONDecodeError:
                all_events.append({"Action": "unparsed", "Output": line})
    log = output / "go-test.jsonl"
    log.write_text("".join(logs), encoding="utf-8", newline="\n")
    passed_tests = {
        (str(event.get("Package")), str(event.get("Test")))
        for event in all_events
        if event.get("Action") == "pass" and event.get("Test") and "/" not in str(event.get("Test"))
    }
    failed_tests = [
        {"package": event.get("Package"), "test": event.get("Test")}
        for event in all_events
        if event.get("Action") == "fail" and event.get("Test") and "/" not in str(event.get("Test"))
    ]
    expected = int(manifest["total_go_tests"])
    passed = not failed_tests and all(code == 0 for code in exit_codes) and len(passed_tests) == expected
    record = {
        "schema": "AgentTool.V12ApplicationObservabilityGoGate/1",
        "manifest_sha256": sha(manifest_path),
        "gopath": str(args.gopath.resolve()),
        "commands": commands,
        "started_ns": started,
        "ended_ns": time.time_ns(),
        "expected_tests": expected,
        "passed_tests": len(passed_tests),
        "failed_tests": failed_tests,
        "exit_codes": exit_codes,
        "log_sha256": sha(log),
        "status": "PASS" if passed else "FAIL",
        "classifier_training_runs": 0,
        "real_auc_calculations": 0,
        "timing_confirmatory_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    (output / "gate.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

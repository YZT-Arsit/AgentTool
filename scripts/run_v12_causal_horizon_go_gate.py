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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--go-root", type=Path, required=True)
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
    env = os.environ.copy()
    env.update(
        {
            "GO111MODULE": "off",
            "GOPATH": "/root/autodl-tmp/v9-gopath",
            "GOPROXY": "off",
            "GONOSUMDB": "*",
        }
    )
    all_events: list[dict[str, object]] = []
    commands: list[list[str]] = []
    exit_codes: list[int] = []
    started = time.time_ns()
    for package, tests in manifest["packages"].items():
        command = [str(args.go), "test", "-count=1", "-timeout=10m", "-json"]
        if isinstance(tests, list):
            pattern = "^(?:" + "|".join(re.escape(test) for test in tests) + ")$"
            command.extend(["-run", pattern])
        command.append(package_paths[package])
        commands.append(command)
        result = subprocess.run(
            command,
            cwd=args.go_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        exit_codes.append(result.returncode)
        with (output / "go-test.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(result.stdout)
        for line in result.stdout.splitlines():
            try:
                all_events.append(json.loads(line))
            except json.JSONDecodeError:
                all_events.append({"Action": "unparsed", "Output": line})
        if result.returncode != 0:
            break
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
    passed = not failed_tests and all(code == 0 for code in exit_codes) and len(passed_tests) == manifest["test_count"]
    record = {
        "schema": "AgentTool.V12CausalHorizonGoGate/1",
        "manifest_sha256": sha(manifest_path),
        "commands": commands,
        "started_ns": started,
        "ended_ns": time.time_ns(),
        "expected_tests": manifest["test_count"],
        "passed_tests": len(passed_tests),
        "failed_tests": failed_tests,
        "exit_codes": exit_codes,
        "log_sha256": sha(output / "go-test.jsonl"),
        "status": "PASS" if passed else "FAIL",
        "timing_attack_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    (output / "gate.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

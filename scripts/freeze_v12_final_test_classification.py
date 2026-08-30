from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "fd2dd3a6e63a47ee98c9708052f979fa35ebf47f"
SOURCE = ROOT / "V12_3_TEST_CLASSIFICATION.json"
NEW_TEST = "tests/test_v12_final_runtime.py"

LEGACY_FILES = {
    "tests/test_semantic_harness_v3.py",
    "tests/test_v10_1_executor.py",
    "tests/test_v10_holdout_harness.py",
}
HISTORICAL_FILES = {
    "tests/test_v11b0_driver.py",
    "tests/test_v11b0_1_hardening.py",
}
V11_FULL_SCOPE_CURRENT = {
    "tests/test_v11_full_scope.py::test_microsoft_handoff_is_absent_not_invented",
    "tests/test_v11_full_scope.py::test_structural_generator_binds_effect_semantics",
}


def git_bytes(path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{BASE_COMMIT}:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def collect_nodes() -> list[str]:
    completed = subprocess.run(
        ["python", "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        line.strip().replace("\\", "/")
        for line in completed.stdout.splitlines()
        if line.startswith("tests/")
    ]


def classify(node_id: str, old: dict[str, dict[str, object]]) -> tuple[str, str]:
    path = node_id.split("::", 1)[0]
    if path == NEW_TEST:
        return (
            "V12_CURRENT_RUNTIME",
            "executes the actual v11a_confirmatory orchestrator, CanonicalOnlineSession, "
            "OnlineSimplePIRResolver, pinned native framework, or frozen prebuilt PIR path",
        )
    if path in LEGACY_FILES:
        return (
            "LEGACY_COMPATIBILITY",
            "historical semantic/protocol executor not transitively reachable from selected V12 execution",
        )
    if path in HISTORICAL_FILES:
        return "HISTORICAL_EVIDENCE", "V11B driver/freeze contract retained as immutable historical evidence"
    if path == "tests/test_v11_full_scope.py" and node_id not in V11_FULL_SCOPE_CURRENT:
        return (
            "LEGACY_COMPATIBILITY",
            "uses the static canonical_external_outcome/canonical_implementation path rather than CanonicalOnlineSession",
        )
    prior = old[node_id]["test_class"]
    if prior == "CURRENT_SYSTEM_EXECUTION_REACHABLE":
        return "V12_CURRENT_RUNTIME", str(old[node_id]["reason"])
    if prior == "PLATFORM_SPECIFIC_PORTABILITY":
        return "PLATFORM_PORTABILITY", str(old[node_id]["reason"])
    return "HISTORICAL_EVIDENCE", str(old[node_id]["reason"])


def main() -> int:
    old_value = json.loads(SOURCE.read_text(encoding="utf-8"))
    old = {row["node_id"]: row for row in old_value["nodes"]}
    nodes = collect_nodes()
    if len(nodes) != 318 or len(set(nodes)) != 318:
        raise RuntimeError(f"expected 318 unique nodes after adding 16 V12-FINAL tests, got {len(nodes)}")
    if set(old) - set(nodes):
        raise RuntimeError("a frozen V12.3 node disappeared")

    source_hashes: dict[str, str] = {}
    entries = []
    for node_id in nodes:
        path = node_id.split("::", 1)[0]
        if path not in source_hashes:
            content = (ROOT / path).read_bytes() if path == NEW_TEST else git_bytes(path)
            source_hashes[path] = sha256_bytes(content)
        test_class, reason = classify(node_id, old)
        entries.append(
            {
                "node_id": node_id,
                "source_path": path,
                "source_sha256": source_hashes[path],
                "test_class": test_class,
                "reason": reason,
            }
        )

    counts: dict[str, int] = {}
    for row in entries:
        counts[row["test_class"]] = counts.get(row["test_class"], 0) + 1
    if sum(counts.values()) != 318:
        raise RuntimeError("classification denominator changed")
    v10_nodes = [row for row in entries if row["source_path"] == "tests/test_v10_1_executor.py"]
    if len(v10_nodes) != 14 or any(row["test_class"] != "LEGACY_COMPATIBILITY" for row in v10_nodes):
        raise RuntimeError("V10.1 compatibility nodes were not mechanically separated")
    current = [row for row in entries if row["test_class"] == "V12_CURRENT_RUNTIME"]
    new_current = [row for row in current if row["source_path"] == NEW_TEST]
    if len(new_current) != 16:
        raise RuntimeError("actual V12-path replacement coverage is incomplete")

    value = {
        "schema": "AgentTool.V12Final.TestClassification/1",
        "base_commit": BASE_COMMIT,
        "runtime_reachability_sha256": hashlib.sha256(
            (ROOT / "V12_FINAL_RUNTIME_REACHABILITY.json").read_bytes()
        ).hexdigest(),
        "frozen_before_v12_final_execution": True,
        "classification_basis": "mechanical transitive reachability from the selected V12 driver",
        "counts": counts,
        "nodes": entries,
        "selected_v12_cases_executed": 0,
    }
    path = ROOT / "V12_FINAL_TEST_CLASSIFICATION.json"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"counts": counts, "current_runtime_nodes": len(current)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

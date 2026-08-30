from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "903728276e0ece3731f044543dacdf66b363d324"
SOURCE = ROOT / "V12_2_TEST_CLASSIFICATION.json"
V12_2_SERIAL = ROOT / "V12_2_LINUX_SERIAL_GATE.json"
TARGET_NODE = (
    "tests/test_v11b0_driver.py::V11B0DriverTests::"
    "test_selected_execution_is_impossible_without_independent_approval"
)
TARGET_REASON = (
    "historical pre-V11B output-root absence guard; V11B has permanently executed "
    "and its failed output root is intentionally preserved"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_exclusive(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    nodes = source["nodes"]
    if len(nodes) != 302 or len({row["node_id"] for row in nodes}) != 302:
        raise RuntimeError("V12.2 classification is not the frozen 302-node corpus")

    corrected = []
    corrections = 0
    for original in nodes:
        row = dict(original)
        if row["node_id"] == TARGET_NODE:
            if row["test_class"] != "CURRENT_SYSTEM_EXECUTION_REACHABLE":
                raise RuntimeError("V11B0 guard did not have the frozen V12.2 Class-A status")
            row["test_class"] = "HISTORICAL_EVIDENCE_AUDIT"
            row["reason"] = TARGET_REASON
            corrections += 1
        corrected.append(row)
    if corrections != 1:
        raise RuntimeError(f"expected exactly one correction, got {corrections}")

    for before, after in zip(nodes, corrected, strict=True):
        if before["node_id"] == TARGET_NODE:
            continue
        if before != after:
            raise RuntimeError(f"unexpected classification drift: {before['node_id']}")

    counts: dict[str, int] = {}
    for row in corrected:
        counts[row["test_class"]] = counts.get(row["test_class"], 0) + 1
    expected_counts = {
        "CURRENT_SYSTEM_EXECUTION_REACHABLE": 116,
        "HISTORICAL_EVIDENCE_AUDIT": 176,
        "PLATFORM_SPECIFIC_PORTABILITY": 10,
    }
    if counts != expected_counts:
        raise RuntimeError(f"unexpected V12.3 classification counts: {counts}")

    serial = json.loads(V12_2_SERIAL.read_text(encoding="utf-8"))
    retained_ids = {
        node_id
        for node_id in serial["failed_nodes"]
        if node_id.startswith("tests/test_v10_1_executor.py::")
    }
    if len(retained_ids) != 11:
        raise RuntimeError(f"expected 11 previously failing V10.1 nodes, got {len(retained_ids)}")
    corrected_by_id = {row["node_id"]: row for row in corrected}
    if any(
        corrected_by_id[node_id]["test_class"] != "CURRENT_SYSTEM_EXECUTION_REACHABLE"
        for node_id in retained_ids
    ):
        raise RuntimeError("a previously failing V10.1 node was removed from Class A")

    classification = {
        "schema": "AgentTool.V12_3.TestClassification/1",
        "base_commit": BASE_COMMIT,
        "source_v12_2_classification_sha256": sha256(SOURCE),
        "classification_frozen_before_v12_3_execution": True,
        "semantic_corrections": [
            {
                "node_id": TARGET_NODE,
                "from": "CURRENT_SYSTEM_EXECUTION_REACHABLE",
                "to": "HISTORICAL_EVIDENCE_AUDIT",
                "reason": TARGET_REASON,
            }
        ],
        "all_other_nodes_byte_semantically_unchanged": True,
        "counts": counts,
        "nodes": corrected,
        "selected_v12_cases_executed": 0,
    }
    classification_path = ROOT / "V12_3_TEST_CLASSIFICATION.json"
    write_json_exclusive(classification_path, classification)

    class_a = [row for row in corrected if row["test_class"] == "CURRENT_SYSTEM_EXECUTION_REACHABLE"]
    manifest = {
        "schema": "AgentTool.V12_3.LinuxClassAManifest/1",
        "base_commit": BASE_COMMIT,
        "classification_sha256": sha256(classification_path),
        "frozen_before_targeted_and_decisive_execution": True,
        "node_count": len(class_a),
        "allowed_skips": 0,
        "required_result": "ALL_PASS",
        "nodes": class_a,
        "selected_v12_cases_executed": 0,
    }
    manifest_path = ROOT / "V12_3_LINUX_CLASS_A_MANIFEST.json"
    write_json_exclusive(manifest_path, manifest)

    md = """# V12.3 Test Classification

Frozen before V12.3 execution from the immutable V12.2 302-node classification.

- `CURRENT_SYSTEM_EXECUTION_REACHABLE`: 116
- `HISTORICAL_EVIDENCE_AUDIT`: 176
- `PLATFORM_SPECIFIC_PORTABILITY`: 10

Exactly one semantic correction was made: the V11B0 prestart output-root guard is historical because V11B has permanently executed and its failed output root is intentionally retained. The historical test itself is unchanged.

All eleven `tests/test_v10_1_executor.py` nodes remain current-system execution-reachable. No other node changed class or reason.
"""
    (ROOT / "V12_3_TEST_CLASSIFICATION.md").write_text(md, encoding="utf-8", newline="\n")
    print(json.dumps({"counts": counts, "class_a_manifest_sha256": sha256(manifest_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

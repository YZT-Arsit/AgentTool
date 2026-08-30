from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION = ROOT / "V12_FINAL_TEST_CLASSIFICATION.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    value = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    nodes = [row for row in value["nodes"] if row["test_class"] == "V12_CURRENT_RUNTIME"]
    if len(nodes) != 70 or len({row["node_id"] for row in nodes}) != 70:
        raise RuntimeError(f"expected 70 frozen current-runtime nodes, got {len(nodes)}")
    if any(row["source_path"] == "tests/test_v10_1_executor.py" for row in nodes):
        raise RuntimeError("legacy V10.1 source-run node entered current-runtime manifest")
    if any(row["source_path"] == "tests/test_v11b0_driver.py" for row in nodes):
        raise RuntimeError("historical V11B prestart/driver node entered current-runtime manifest")
    if sum(row["source_path"] == "tests/test_v12_final_runtime.py" for row in nodes) != 16:
        raise RuntimeError("actual V12-path replacement coverage is incomplete")
    manifest = {
        "schema": "AgentTool.V12Final.LinuxCurrentRuntimeClassAManifest/1",
        "classification_sha256": sha256(CLASSIFICATION),
        "runtime_reachability_sha256": sha256(ROOT / "V12_FINAL_RUNTIME_REACHABILITY.json"),
        "frozen_after_scoped_legacy_and_no_go_path_qualification": True,
        "frozen_before_decisive_current_runtime_execution": True,
        "node_count": len(nodes),
        "allowed_skips": 0,
        "required_result": "ALL_PASS",
        "nodes": nodes,
        "selected_v12_cases_executed": 0,
    }
    path = ROOT / "V12_FINAL_LINUX_CLASS_A_MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"node_count": len(nodes), "sha256": sha256(path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

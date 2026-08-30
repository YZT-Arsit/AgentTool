from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_CLASSIFICATION = ROOT / "V12_FINAL_TEST_CLASSIFICATION.json"
BASE_MANIFEST = ROOT / "V12_FINAL_LINUX_CLASS_A_MANIFEST.json"
NEW_TEST_SOURCE = ROOT / "tests" / "test_v12_rc_invocation_routing.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_new_nodes() -> list[str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(NEW_TEST_SOURCE.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    nodes = [line.strip() for line in completed.stdout.splitlines() if line.startswith("tests/") and "::" in line]
    if len(nodes) != 15 or len(set(nodes)) != 15:
        raise RuntimeError(f"expected 15 V12-RC invocation-routing nodes, got {len(nodes)}")
    return nodes


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    base = json.loads(BASE_CLASSIFICATION.read_text(encoding="utf-8"))
    old_manifest = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    old_nodes = list(old_manifest["nodes"])
    if len(old_nodes) != 70:
        raise RuntimeError("V12-FINAL Class-A baseline is not the frozen 70-node set")
    source_hash = sha256(NEW_TEST_SOURCE)
    additions = [
        {
            "node_id": node,
            "source_path": "tests/test_v12_rc_invocation_routing.py",
            "source_sha256": source_hash,
            "test_class": "V12_CURRENT_RUNTIME",
            "reason": "private framework-routing identity, repeated logical Tool operation fidelity, and public-view non-interference",
        }
        for node in collect_new_nodes()
    ]
    classification_nodes = list(base["nodes"]) + additions
    counts = dict(base["counts"])
    counts["V12_CURRENT_RUNTIME"] = 85
    classification = {
        "schema": "AgentTool.V12RC.TestClassification/1",
        "base_commit": "c20fa6adf23ba652f5c4c8b82a566788032cfd82",
        "supersedes_for_v12_rc_only": BASE_CLASSIFICATION.name,
        "v12_final_negative_evidence_unchanged": True,
        "classification_frozen_before_v12_rc_decisive_execution": True,
        "counts": counts,
        "nodes": classification_nodes,
        "selected_v12_cases_executed": 0,
    }
    classification_path = ROOT / "V12_RC_TEST_CLASSIFICATION.json"
    write_json(classification_path, classification)
    combined = old_nodes + additions
    if len(combined) != 85 or len({row["node_id"] for row in combined}) != 85:
        raise RuntimeError("V12-RC Class-A manifest is not exactly 85 unique nodes")
    if [row["node_id"] for row in combined[:70]] != [row["node_id"] for row in old_nodes]:
        raise RuntimeError("an unrelated current-runtime node was removed or reordered")
    manifest = {
        "schema": "AgentTool.V12RC.LinuxCurrentRuntimeClassAManifest/1",
        "base_v12_final_manifest_sha256": sha256(BASE_MANIFEST),
        "classification_sha256": sha256(classification_path),
        "frozen_before_decisive_current_runtime_execution": True,
        "node_count": 85,
        "allowed_skips": 0,
        "required_result": "ALL_PASS",
        "nodes": combined,
        "selected_v12_cases_executed": 0,
    }
    manifest_path = ROOT / "V12_RC_LINUX_CLASS_A_MANIFEST.json"
    write_json(manifest_path, manifest)
    print(json.dumps({"nodes": 85, "classification_sha256": sha256(classification_path), "manifest_sha256": sha256(manifest_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

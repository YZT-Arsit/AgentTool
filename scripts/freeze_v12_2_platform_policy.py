from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "bdbb35b873ebf5c660b288b391abe320c3963d99"

# Frozen before any V12.2 decisive execution.  Eligibility is file-based and
# therefore cannot react to individual test outcomes.
CLASS_A_FILES = {
    "tests/test_semantic_harness_v3.py": "framework semantic projection and deterministic adapter contract",
    "tests/test_v7_ohttp_architecture.py": "RFC9458 action mediation, routing, and reliable-result contract",
    "tests/test_v8_standards_closure.py": "RFC9292/RFC9458 canonical standards path",
    "tests/test_v9_1_public_profile.py": "public profile, connection, lifetime, structural, and size projection",
    "tests/test_v10_1_executor.py": "native/canonical semantic executor and structural executor contract",
    "tests/test_v10_holdout_harness.py": "confirmatory loader and semantic comparison contract",
    "tests/test_v11_3_profile.py": "online Agent session admission and profile contract",
    "tests/test_v11_4_profile.py": "final online profile and causal session contract",
    "tests/test_v11_full_scope.py": "current native/canonical framework, routing, effect, and multi-action path",
    "tests/test_v11a_1_prefix_projection.py": "corrected structural-prefix projection",
    "tests/test_v11a_confirmatory.py": "generic confirmatory orchestrator and structural verdict contract",
    "tests/test_v11b0_1_hardening.py": "artifact integrity, exact operation validation, and summarizer contract",
    "tests/test_v11b0_driver.py": "one-shot append-only execution driver contract",
    "tests/test_v12_closure.py": "V12 runtime dependency, permit, profile binding, and requalification contract",
}

CLASS_C_FILES = {
    "tests/test_stage10.py": "Windows-only historical .venv-stage10/Scripts/python.exe layout",
}
CLASS_C_NODES = {
    "tests/test_stage9.py::Stage9AdaptiveTests::test_l2_public_runtime_existing_approval_path": (
        "Windows-only historical .venv-stage9/Scripts/python.exe layout"
    ),
}

KNOWN_PRIOR_LINUX_FAILURES = {
    "tests/test_crypto_closure.py::test_real_pir_100k_was_correct_and_fully_preprocessed",
    "tests/test_crypto_closure.py::test_server_trace_excludes_private_labels_and_uses_fresh_queries",
    "tests/test_crypto_closure.py::test_recovered_capsule_feeds_the_common_executor",
    "tests/test_crypto_closure.py::test_action_structural_and_size_results_are_at_chance",
    "tests/test_interrupted_timing_analysis.py::test_pir_aggregation_uses_only_constant_target_profiles",
    "tests/test_interrupted_timing_analysis.py::test_tool_blocks_exclude_padding_slots",
    "tests/test_stage9.py::Stage9AdaptiveTests::test_l2_public_runtime_existing_approval_path",
    "tests/test_timing_closure.py::test_confirmatory_profiles_were_frozen",
    "tests/test_timing_closure.py::test_gateway_host_trace_has_fixed_bidirectional_frames_and_one_destination",
    "tests/test_timing_closure.py::test_noop_cover_does_not_produce_heavy_work_or_effect",
    "tests/test_timing_closure.py::test_real_tool_operations_complete_once_without_dummy_heavy_ops",
    "tests/test_timing_closure.py::test_pir_schedule_runs_real_and_dummy_queries_through_same_server_path",
    "tests/test_timing_closure.py::test_pir_correctness_and_fresh_randomness_remain_intact",
    "tests/test_timing_closure.py::test_nominal_public_deadlines_do_not_depend_on_private_label",
}


def git_bytes(path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{BASE_COMMIT}:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def collect_nodes() -> list[str]:
    completed = subprocess.run(
        ["python", "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.startswith("tests/")]


def classify(node_id: str) -> tuple[str, str]:
    path = node_id.split("::", 1)[0]
    if node_id in CLASS_C_NODES:
        return "PLATFORM_SPECIFIC_PORTABILITY", CLASS_C_NODES[node_id]
    if path in CLASS_C_FILES:
        return "PLATFORM_SPECIFIC_PORTABILITY", CLASS_C_FILES[path]
    if path in CLASS_A_FILES:
        return "CURRENT_SYSTEM_EXECUTION_REACHABLE", CLASS_A_FILES[path]
    return (
        "HISTORICAL_EVIDENCE_AUDIT",
        "historical V1-V11 implementation/result contract outside the selected V12 runtime path",
    )


def main() -> int:
    nodes = collect_nodes()
    if len(nodes) != 302 or len(set(nodes)) != 302:
        raise RuntimeError(f"expected exactly 302 unique nodes, got {len(nodes)}")
    source_hashes: dict[str, str] = {}
    entries = []
    for node_id in nodes:
        path = node_id.split("::", 1)[0]
        source_hashes.setdefault(path, hashlib.sha256(git_bytes(path)).hexdigest())
        test_class, reason = classify(node_id)
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
    for item in entries:
        counts[item["test_class"]] = counts.get(item["test_class"], 0) + 1
    prior = {item["node_id"]: item["test_class"] for item in entries if item["node_id"] in KNOWN_PRIOR_LINUX_FAILURES}
    if set(prior) != KNOWN_PRIOR_LINUX_FAILURES:
        raise RuntimeError("prior Linux failure set does not match the frozen 302-node collection")
    if any(value == "CURRENT_SYSTEM_EXECUTION_REACHABLE" for value in prior.values()):
        raise RuntimeError("a known historical artifact/layout failure was classified as Class A")

    classification = {
        "schema": "AgentTool.V12_2.TestClassification/1",
        "base_commit": BASE_COMMIT,
        "classification_frozen_before_decisive_execution": True,
        "seed_or_outcome_used": False,
        "counts": counts,
        "known_prior_linux_repository_failures": prior,
        "nodes": entries,
    }
    (ROOT / "V12_2_TEST_CLASSIFICATION.json").write_text(
        json.dumps(classification, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    class_a = [item for item in entries if item["test_class"] == "CURRENT_SYSTEM_EXECUTION_REACHABLE"]
    manifest = {
        "schema": "AgentTool.V12_2.LinuxClassATestManifest/1",
        "base_commit": BASE_COMMIT,
        "frozen_before_first_decisive_execution": True,
        "node_count": len(class_a),
        "nodes": class_a,
        "allowed_skips": 0,
        "required_result": "ALL_PASS",
    }
    (ROOT / "V12_2_LINUX_TEST_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"counts": counts, "class_a": len(class_a)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

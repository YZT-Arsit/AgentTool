from __future__ import annotations

import hashlib
import importlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SHA = "14eb0488813425a99e49ac74741777fb5022a04ada6577a5b00bb5d2ef119877"
SIMPLEPIR_SHA = "2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_tree(source: Path) -> tuple[str, int]:
    entries = []
    for path in sorted(
        (item for item in source.rglob("*") if item.is_file() and ".git" not in item.relative_to(source).parts),
        key=lambda item: item.relative_to(source).as_posix(),
    ):
        entries.append((sha256(path), path.stat().st_size, path.relative_to(source).as_posix()))
    text = "".join(f"{digest} {size} {name}\n" for digest, size, name in entries)
    return hashlib.sha256(text.encode()).hexdigest(), len(entries)


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command(*args: str) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        return f"NOT_AVAILABLE:{type(exc).__name__}"


def environment_freeze() -> dict[str, Any]:
    agents = Path(importlib.import_module("agents").__file__).resolve()
    microsoft = Path(importlib.import_module("agent_framework").__file__).resolve()
    value = {
        "schema": "AgentTool.V12ExecutionEnvironmentFreeze/1",
        "platform": platform.platform(),
        "uname": command("uname", "-a"),
        "cpu": command("lscpu"),
        "python_version": command(sys.executable, "--version"),
        "go_version_in_runtime_path": command("go", "version"),
        "gcc_version": command("gcc", "--version").splitlines()[0],
        "openai": {
            "revision": "a40ae9803e6b7a79faa246293f56adb100d5868b",
            "import_path": agents.relative_to(ROOT).as_posix(),
            "import_sha256": sha256(agents),
        },
        "microsoft": {
            "revision": "af461de51da16f5cb800ff7febc0f8f96355607a",
            "import_path": microsoft.relative_to(ROOT).as_posix(),
            "import_sha256": sha256(microsoft),
        },
        "simplepir_revision": "e9020b03bf2872c75b8954e749e32408b5db87ed",
        "simplepir_bridge_sha256": SIMPLEPIR_SHA,
        "canonical_linux_runner_sha256": CANONICAL_SHA,
        "ohttp_revision": "776f22a178b8332f4acacc2919176df8e61046cc",
        "public_profile_sha256": sha256(ROOT / "PUBLIC_PROFILE_ONLINE_V11_4.json"),
        "selected_v12_cases_executed": 0,
        "timing_privacy": "OPEN / NOT TESTED",
        "packet_level_timing": "OPEN",
        "hardware_tee": "NOT_TESTED",
    }
    write_json(ROOT / "V12_EXECUTION_ENVIRONMENT_FREEZE.json", value)
    return value


def execution_files() -> list[Path]:
    fixed = [
        "scripts/run_v12_confirmatory.py",
        "scripts/summarize_v12_confirmatory.py",
        "scripts/run_v12_profile_requalification.py",
        "scripts/run_v11_2_online_development.py",
        "scripts/run_v11_3_profile_closure.py",
        "scripts/run_v11_4_profile_qualification.py",
        "V12_FINAL_DECISION_RULES.json",
        "V12_EXECUTION_PLAN.json",
        "V12_EXECUTION_ORDER.json",
        "V12_SELECTION_SEEDS.json",
        "V12_MASTER_EXCLUSION_SET.json",
        "V12_CANDIDATE_UNIVERSES_FREEZE.json",
        "V12_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json",
        "V12_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json",
        "V12_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json",
        "V12_EFFECT_CONTRACT_HOLDOUT_FREEZE.json",
        "V12_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json",
        "V12_EXECUTION_ENVIRONMENT_FREEZE.json",
        "V12_SIMPLEPIR_RUNTIME_CLOSURE.json",
        "PUBLIC_PROFILE_ONLINE_V11_4.json",
        "pir_integration/simplepir_bridge/main.go",
        "pir_integration/simplepir_bridge/go.mod",
        "v10_holdout/harness.py",
        "v12_development/resources.py",
    ]
    package_roots = (
        "action_privacy_v8",
        "canonical_v9",
        "canonical_v9_1",
        "cryptographic_closure",
        "v11_3",
        "v11_4",
        "v11_full_scope",
        "v11_online",
        "v11a_confirmatory",
    )
    paths = [ROOT / item for item in fixed]
    for package in package_roots:
        paths.extend(sorted((ROOT / package).glob("*.py")))
    unique = sorted(set(paths), key=lambda item: item.relative_to(ROOT).as_posix())
    missing = [path for path in unique if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    return unique


def artifact_manifest(environment: dict[str, Any]) -> dict[str, Any]:
    runner = ROOT / "common_action_gateway_v2/bin/canonical-v11_4-runner"
    bridge = ROOT / "pir_integration/simplepir_bridge/acv-simplepir-online"
    if sha256(runner) != CANONICAL_SHA or sha256(bridge) != SIMPLEPIR_SHA:
        raise RuntimeError("frozen Linux binary hash mismatch")
    simplepir_hash, simplepir_files = source_tree(ROOT / "external_pir/simplepir")
    ohttp_hash, ohttp_files = source_tree(ROOT / "third_party/ohttp-go")
    value = {
        "schema": "AgentTool.V12ExecutionArtifactManifest/1",
        "status": "FROZEN_FOR_V12_EXECUTION",
        "historical_source_commit": "5294978fdf1a8cfd35e04b2e1e9b08158fc435e3",
        "files": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}
            for path in execution_files()
        ],
        "binaries": {
            "canonical_runner": {"path": runner.relative_to(ROOT).as_posix(), "sha256": CANONICAL_SHA},
            "simplepir_bridge": {"path": bridge.relative_to(ROOT).as_posix(), "sha256": SIMPLEPIR_SHA},
        },
        "framework_imports": {
            "openai": {
                "path": environment["openai"]["import_path"],
                "source_root_relative": "external_stage10/openai-agents-python",
                "revision": environment["openai"]["revision"],
                "sha256": environment["openai"]["import_sha256"],
            },
            "microsoft": {
                "path": environment["microsoft"]["import_path"],
                "source_root_relative": "external_stage9/agent-framework",
                "revision": environment["microsoft"]["revision"],
                "sha256": environment["microsoft"]["import_sha256"],
            },
        },
        "source_trees": {
            "simplepir": {
                "path": "external_pir/simplepir",
                "revision": environment["simplepir_revision"],
                "sha256": simplepir_hash,
                "file_count": simplepir_files,
            },
            "ohttp": {
                "path": "third_party/ohttp-go",
                "revision": environment["ohttp_revision"],
                "sha256": ohttp_hash,
                "file_count": ohttp_files,
            },
        },
        "selection_and_plan": {
            "selected_units": 134,
            "native_units": 53,
            "canonical_units": 81,
            "selected_v12_cases_executed": 0,
        },
        "preflight_policy": {
            "artifact_bytes_required": True,
            "capability_preflight_before_permit": True,
            "resource_preflight_before_permit": True,
            "results_root_must_not_exist": True,
            "retry": False,
        },
    }
    value["manifest_payload_sha256"] = canonical_sha(value)
    write_json(ROOT / "V12_EXECUTION_ARTIFACT_MANIFEST.json", value)
    return value


def final_freeze(manifest: dict[str, Any]) -> dict[str, Any]:
    bound_names = (
        "V11B_RESULT_TREE_MANIFEST.json",
        "V12_DEVELOPMENT_EVALUATION_SUMMARY.json",
        "V12_MASTER_EXCLUSION_SET.json",
        "V12_CANDIDATE_UNIVERSES_FREEZE.json",
        "V12_SELECTION_SEEDS.json",
        "V12_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json",
        "V12_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json",
        "V12_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json",
        "V12_EFFECT_CONTRACT_HOLDOUT_FREEZE.json",
        "V12_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json",
        "V12_EXECUTION_ORDER.json",
        "V12_EXECUTION_PLAN.json",
        "V12_FINAL_DECISION_RULES.json",
        "V12_EXECUTION_ENVIRONMENT_FREEZE.json",
        "V12_EXECUTION_ARTIFACT_MANIFEST.json",
        "scripts/run_v12_confirmatory.py",
        "scripts/summarize_v12_confirmatory.py",
    )
    if (ROOT / "results_v12_confirmatory").exists():
        raise RuntimeError("selected V12 result root exists")
    value = {
        "schema": "AgentTool.V12FinalConfirmatoryFreeze/1",
        "status": "FROZEN_PREEXECUTION_ONLY",
        "bound_files": {name: sha256(ROOT / name) for name in bound_names},
        "artifact_manifest_payload_sha256": manifest["manifest_payload_sha256"],
        "selected_counts": {"s1": 20, "s2": 12, "s3": 12, "s4": 9, "structural_pairs": 14},
        "execution_units": {"total": 134, "native": 53, "canonical": 81},
        "seed_search": False,
        "selected_v12_cases_executed": 0,
        "authorization_file_created": False,
        "results_v12_confirmatory_exists": False,
        "timing_privacy": "OPEN / NOT TESTED",
        "packet_level_timing": "OPEN",
        "hardware_tee": "NOT_TESTED",
        "source_body_executable_subset": 0,
        "source_body_equivalence_go": False,
        "ready_for_independent_v12_freeze_audit": True,
    }
    value["aggregate_sha256"] = canonical_sha(value)
    write_json(ROOT / "V12_FINAL_CONFIRMATORY_FREEZE.json", value)
    return value


def main() -> None:
    development = json.loads((ROOT / "V12_DEVELOPMENT_EVALUATION_SUMMARY.json").read_text())
    if development.get("ready_for_holdout_freeze") is not True:
        raise RuntimeError("development gates are not closed")
    environment = environment_freeze()
    manifest = artifact_manifest(environment)
    freeze = final_freeze(manifest)
    print(json.dumps({"status": freeze["status"], "units": 134, "selected_executed": 0}))


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "fd2dd3a6e63a47ee98c9708052f979fa35ebf47f"
ACTUAL_FILES = (
    "scripts/run_v12_confirmatory.py",
    "v11a_confirmatory/orchestrator.py",
    "v11_online/session.py",
    "v11_online/frameworks.py",
    "v11_full_scope/frameworks.py",
    "v11_full_scope/canonical.py",
)
LEGACY_FILES = (
    "v10_1_executor/semantic.py",
    "v10_1_executor/canonical_bridge.py",
    "v10_1_executor/structural.py",
    "canonical_v9/runner.py",
    "cryptographic_closure/pir_backend.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    actual_orchestrator = source("v11a_confirmatory/orchestrator.py")
    online_session = source("v11_online/session.py")
    legacy_semantic = source("v10_1_executor/semantic.py")
    legacy_bridge = source("v10_1_executor/canonical_bridge.py")
    canonical_runner = source("canonical_v9/runner.py")
    legacy_pir = source("cryptographic_closure/pir_backend.py")

    checks = {
        "actual_orchestrator_calls_online_session": (
            "CanonicalOnlineSession(" in actual_orchestrator
            and "run_canonical_semantic_case" in actual_orchestrator
            and "run_canonical_online_trajectory_case" in actual_orchestrator
            and "run_structural_arm" in actual_orchestrator
        ),
        "online_resolver_selects_prebuilt_binary": (
            '"acv-simplepir-online"' in online_session
            and 'command = [str(prebuilt_bridge), "--interactive"]' in online_session
        ),
        "linux_online_source_fallback_disabled": (
            "online SimplePIR requires the frozen prebuilt bridge; source fallback is disabled"
            in online_session
        ),
        "actual_callers_do_not_reference_run_simplepir": (
            "run_simplepir" not in actual_orchestrator and "run_simplepir" not in online_session
        ),
        "online_session_imports_only_simplepir_commit_constant": (
            "from cryptographic_closure.pir_backend import SIMPLEPIR_COMMIT" in online_session
        ),
        "legacy_semantic_constructs_canonical_bridge": "CanonicalSemanticBridge" in legacy_semantic,
        "legacy_bridge_calls_real_pir_select": "real_pir_select(" in legacy_bridge,
        "legacy_real_pir_select_calls_run_simplepir": "run_simplepir(" in canonical_runner,
        "legacy_pir_uses_go_run": 'str(go_executable), "run", "."' in legacy_pir,
    }
    if not all(checks.values()):
        raise RuntimeError(f"runtime reachability assertion failed: {checks}")

    hashes = {
        path: {"sha256": sha256(ROOT / path), "bytes": (ROOT / path).stat().st_size}
        for path in (*ACTUAL_FILES, *LEGACY_FILES)
    }
    value = {
        "schema": "AgentTool.V12Final.RuntimeReachability/1",
        "base_commit": BASE_COMMIT,
        "frozen_before_decisive_v12_final_execution": True,
        "checks": checks,
        "actual_selected_runtime": {
            "edges": [
                "scripts.run_v12_confirmatory.execute_unit -> v11a_confirmatory.orchestrator",
                "run_canonical_semantic_case -> CanonicalOnlineSession",
                "run_canonical_online_trajectory_case -> CanonicalOnlineSession",
                "run_structural_arm -> run_canonical_online_trajectory_case",
                "CanonicalOnlineSession -> OnlineSimplePIRResolver",
                "OnlineSimplePIRResolver -> pir_integration/simplepir_bridge/acv-simplepir-online",
            ],
            "prebuilt_bridge": "pir_integration/simplepir_bridge/acv-simplepir-online",
            "calls_cryptographic_closure_pir_backend_run_simplepir": False,
            "imports_simplepir_commit_constant_only": True,
            "go_or_gcc_runtime_discovery": False
        },
        "legacy_v10_1_compatibility": {
            "edges": [
                "v10_1_executor.semantic.run_canonical_case -> CanonicalSemanticBridge",
                "CanonicalSemanticBridge -> canonical_v9.runner.real_pir_select",
                "real_pir_select -> cryptographic_closure.pir_backend.run_simplepir",
                "run_simplepir -> go run .",
            ],
            "requires_go_and_gcc_on_path": True
        },
        "source_files": hashes,
        "selected_v12_cases_executed": 0,
    }
    path = ROOT / "V12_FINAL_RUNTIME_REACHABILITY.json"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    markdown = """# V12 Final Runtime Reachability

The selected V12 path is `scripts.run_v12_confirmatory -> v11a_confirmatory.orchestrator -> CanonicalOnlineSession -> OnlineSimplePIRResolver -> acv-simplepir-online`.

On Linux the online resolver uses the frozen prebuilt bridge and fails closed if it is absent. It imports only `SIMPLEPIR_COMMIT` from the historical PIR module; neither the orchestrator nor online session references or calls `run_simplepir`. Go and GCC discovery are build/legacy concerns, not selected-runtime dependencies.

The separate V10.1 compatibility path is `run_canonical_case -> CanonicalSemanticBridge -> real_pir_select -> run_simplepir -> go run .`. Its PATH/toolchain requirement remains valid legacy regression evidence but is not reachable from selected V12 execution.

All source files, sizes, call edges, and assertions are frozen in the JSON companion before decisive V12-FINAL execution.
"""
    (ROOT / "V12_FINAL_RUNTIME_REACHABILITY.md").write_text(markdown, encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "source_files": len(hashes)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

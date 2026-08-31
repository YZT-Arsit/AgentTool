from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "4a577ec8c4f610e7f9b8fa1b852a518fb4eb2e0c"
PHASE = "V12-TIMING-CAUSAL-HORIZON-REQUALIFICATION"
ENTRYPOINT = Path("scripts/run_v12_causal_horizon_live.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_module_path(name: str) -> Path | None:
    candidate = ROOT / (name.replace(".", "/") + ".py")
    if candidate.is_file():
        return candidate.relative_to(ROOT)
    package = ROOT / name.replace(".", "/") / "__init__.py"
    if package.is_file():
        return package.relative_to(ROOT)
    return None


def python_closure(entry: Path) -> set[Path]:
    pending = [entry]
    found: set[Path] = set()
    while pending:
        relative = pending.pop()
        if relative in found:
            continue
        found.add(relative)
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=str(relative))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.append(node.module)
                names.extend(f"{node.module}.{alias.name}" for alias in node.names)
            for name in names:
                resolved = local_module_path(name)
                if resolved is not None and resolved not in found:
                    pending.append(resolved)
    return found


def files_under(relative: str, suffixes: tuple[str, ...]) -> set[Path]:
    base = ROOT / relative
    return {
        path.relative_to(ROOT)
        for path in base.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes and ".git" not in path.parts
    }


def tracked_external(relative: str) -> set[Path]:
    base = ROOT / relative
    result = subprocess.run(
        ["git", "-C", str(base), "ls-files", "-z"], capture_output=True, check=True
    ).stdout.decode().split("\0")
    return {(base / value).relative_to(ROOT) for value in result if value and (base / value).is_file()}


def add(entries: list[dict[str, object]], relative: Path, role: str) -> None:
    path = ROOT / relative
    entries.append(
        {
            "path": relative.as_posix(),
            "sha256": sha(path),
            "bytes": path.stat().st_size,
            "role": role,
            "reachability_edge": f"{ENTRYPOINT.as_posix()} -> {relative.as_posix()}",
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "V12_CAUSAL_HORIZON_TRANSITIVE_RUNTIME_MANIFEST.json",
    )
    args = parser.parse_args()
    python_files = python_closure(ENTRYPOINT)
    python_files |= {
        Path("scripts/verify_v12_timing_deployment.py"),
        Path("scripts/preflight_v12_pir_lead.py"),
        Path("scripts/run_v12_pir_capacity_development.py"),
        Path("V12_CAUSAL_HORIZON_CAPACITY_MODEL.py"),
        Path("v12_timing/capacity.py"),
    }
    framework_files = files_under("external_stage10/openai-agents-python/src/agents", (".py",))
    framework_files |= files_under(
        "external_stage9/agent-framework/python/packages/core/agent_framework", (".py",)
    )
    go_files = files_under("common_action_gateway_v2", (".go", ".mod", ".sum", ".s"))
    go_files = {path for path in go_files if not path.name.endswith("_test.go")}
    ohttp_files = files_under("third_party/ohttp-go", (".go", ".mod", ".sum", ".s"))
    simplepir_files = tracked_external("external_pir/simplepir")
    protocol_files = {
        Path("V12_CAUSAL_HORIZON_CANDIDATES_FREEZE.json"),
        Path("V12_CAUSAL_HORIZON_PROFILE_FREEZE.json"),
        Path("V12_CAUSAL_HORIZON_CAPACITY_MODEL.json"),
        Path("V12_CAUSAL_HORIZON_LIVE_MANIFEST.json"),
        Path("V12_TIMING_DEVELOPMENT_PROTOCOL.json"),
        Path("V12_TIMING_OBSERVER_PROJECTIONS.json"),
        Path("V12_TIMING_THREAT_MODEL.json"),
    }
    entries: list[dict[str, object]] = []
    for path in sorted(python_files):
        add(entries, path, "PYTHON_TRANSITIVE_RUNTIME")
    for path in sorted(framework_files):
        add(entries, path, "PINNED_NATIVE_FRAMEWORK_SOURCE")
    for path in sorted(go_files):
        add(entries, path, "CANONICAL_GO_RUNNER_BUILD_INPUT")
    for path in sorted(ohttp_files):
        add(entries, path, "OHTTP_GO_BUILD_INPUT")
    for path in sorted(simplepir_files):
        add(entries, path, "SIMPLEPIR_BUILD_INPUT")
    for path in sorted(protocol_files):
        add(entries, path, "FROZEN_TIMING_PROTOCOL_OR_PROFILE")
    binary_paths = (
        Path("common_action_gateway_v2/bin/canonical-v12-causal-horizon-runner"),
        Path("pir_integration/simplepir_bridge/acv-simplepir-v12-timing"),
    )
    for binary in binary_paths:
        if not (ROOT / binary).is_file():
            raise FileNotFoundError(f"required frozen runtime binary unavailable: {binary}")
    payload = {
        "schema": "AgentTool.V12CausalHorizonTransitiveRuntimeManifest/1",
        "phase": PHASE,
        "base_commit": BASE_COMMIT,
        "entrypoint": ENTRYPOINT.as_posix(),
        "enumeration_policy": {
            "python": "recursive static local import closure plus full pinned framework package sources",
            "go": "all non-test Go build inputs under common_action_gateway_v2",
            "simplepir": "all tracked files in pinned external_pir/simplepir repository",
            "ohttp": "all Go build inputs in frozen vendored ohttp-go tree",
        },
        "files": entries,
        "file_count": len(entries),
        "binaries": [
            {
                "path": binary_paths[0].as_posix(),
                "sha256": sha(ROOT / binary_paths[0]),
                "architecture": "linux/amd64",
                "build_provenance": "common_action_gateway_v2/cmd/canonical-v9-runner plus frozen transitive Go build inputs",
            },
            {
                "path": binary_paths[1].as_posix(),
                "sha256": sha(ROOT / binary_paths[1]),
                "architecture": "linux/amd64",
                "build_provenance": "pir_integration/simplepir_bridge plus SimplePIR e9020b03bf2872c75b8954e749e32408b5db87ed",
            },
        ],
        "python_import_probes": {
            "v11_online.session": "v11_online/session.py",
            "v11_online.frameworks": "v11_online/frameworks.py",
            "v12_timing.profile": "v12_timing/profile.py",
            "v12_timing.capacity": "v12_timing/capacity.py",
            "v12_timing.projection": "v12_timing/projection.py",
            "v11a_confirmatory.orchestrator": "v11a_confirmatory/orchestrator.py",
            "agents": "external_stage10/openai-agents-python/src/agents/__init__.py",
            "agent_framework": "external_stage9/agent-framework/python/packages/core/agent_framework/__init__.py",
        },
        "source_binding_policy": "actual imported module.__file__ bytes and resolved executable bytes are authoritative",
        "timing_attack_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    Path("scripts/collect_v12_p10_timing_sentinel.py"),
    Path("scripts/analyze_v12_p10_timing_sentinel.py"),
    Path("scripts/freeze_v12_p10_timing_sentinel.py"),
    Path("scripts/build_v12_p10_sentinel_deployment_manifest.py"),
    Path("scripts/verify_v12_p10_sentinel_deployment.py"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha256(relative: str, *, revision: str = "HEAD") -> str:
    """Hash committed bytes rather than checkout-specific line endings."""

    blob = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(blob).hexdigest()


def local_module_path(name: str) -> Path | None:
    candidate = ROOT / (name.replace(".", "/") + ".py")
    if candidate.is_file():
        return candidate.relative_to(ROOT)
    package = ROOT / name.replace(".", "/") / "__init__.py"
    return package.relative_to(ROOT) if package.is_file() else None


def python_closure(entries: tuple[Path, ...]) -> set[Path]:
    pending, found = list(entries), set()
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
                names.extend([node.module, *(f"{node.module}.{alias.name}" for alias in node.names)])
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
        if path.is_file()
        and path.suffix.lower() in suffixes
        and not path.name.endswith("_test.go")
        and ".git" not in path.parts
    }


def tracked_nested(relative: str) -> set[Path]:
    base = ROOT / relative
    rows = subprocess.run(
        ["git", "-C", str(base), "ls-files", "-z"], check=True, capture_output=True
    ).stdout.decode().split("\0")
    return {
        (base / row).relative_to(ROOT)
        for row in rows
        if row and (base / row).is_file()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build exact P10 sentinel deployment manifest.")
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite deployment manifest: {args.output}")
    if subprocess.run(["git", "diff", "--quiet"], cwd=ROOT, check=False).returncode:
        raise SystemExit("tracked execution source has unstaged changes")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False).returncode:
        raise SystemExit("tracked execution source has staged changes")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    if freeze["execution_source_commit"] != head:
        raise SystemExit("freeze execution-source commit differs from deployment source")
    for relative, expected in freeze["analysis_hashes"].items():
        if git_blob_sha256(relative, revision=head) != expected:
            raise SystemExit(f"freeze analysis source hash mismatch: {relative}")

    files = python_closure(ENTRYPOINTS)
    for relative in (
        "v12_timing",
        "v11_online",
        "v11_full_scope",
        "action_privacy_v8",
        "canonical_v9",
        "canonical_v9_1",
        "cryptographic_closure",
        "v10_holdout",
        "v11_3",
    ):
        files |= files_under(relative, (".py",))
    files |= files_under("external_stage10/openai-agents-python/src/agents", (".py",))
    files |= files_under(
        "external_stage9/agent-framework/python/packages/core/agent_framework", (".py",)
    )
    files |= files_under("common_action_gateway_v2", (".go", ".mod", ".sum", ".s"))
    files |= files_under("third_party/ohttp-go", (".go", ".mod", ".sum", ".s"))
    files |= files_under("pir_integration/simplepir_bridge", (".go", ".mod", ".sum"))
    files |= tracked_nested("external_pir/simplepir")
    files |= {
        Path(value)
        for value in (
            "V12_TIMING_STATISTICAL_PROTOCOL_V2.json",
            "V12_TIMING_OBSERVER_CONTRACT_V2.json",
            "V12_APPLICATION_OBSERVABILITY_DELTA_CANDIDATES_FREEZE.json",
            "V12_APPLICATION_OBSERVABILITY_CAPACITY_FREEZE.json",
            "V12_APPLICATION_OBSERVABILITY_GO_MANIFEST.json",
        )
    }
    entries = [
        {
            "path": path.as_posix(),
            "sha256": sha256(ROOT / path),
            "bytes": (ROOT / path).stat().st_size,
        }
        for path in sorted(files)
    ]
    binaries = (
        Path("common_action_gateway_v2/bin/canonical-v12-delta-functional-runner"),
        Path("pir_integration/simplepir_bridge/acv-simplepir-v12-timing"),
    )
    for path in binaries:
        if not (ROOT / path).is_file():
            raise FileNotFoundError(f"required frozen runtime binary unavailable: {path}")
    probes = {
        "v11_online.session": "v11_online/session.py",
        "v11_online.frameworks": "v11_online/frameworks.py",
        "v12_timing.profile": "v12_timing/profile.py",
        "v12_timing.projection": "v12_timing/projection.py",
        "v12_timing.isolated_tasks": "v12_timing/isolated_tasks.py",
        "v12_timing.sentinel": "v12_timing/sentinel.py",
        "v12_timing.classifier": "v12_timing/classifier.py",
        "v12_timing.statistics": "v12_timing/statistics.py",
        "agents": "external_stage10/openai-agents-python/src/agents/__init__.py",
        "agent_framework": "external_stage9/agent-framework/python/packages/core/agent_framework/__init__.py",
    }
    payload = {
        "schema": "AgentTool.V12P10TimingSentinelDeploymentManifest/1",
        "repository_commit": head,
        "protocol_base_sha": freeze["protocol_base_sha"],
        "freeze_path": args.freeze.name,
        "freeze_sha256": sha256(args.freeze),
        "freeze_payload_sha256": freeze["payload_sha256"],
        "entrypoints": [path.as_posix() for path in ENTRYPOINTS],
        "files": entries,
        "file_count": len(entries),
        "binaries": [
            {
                "path": path.as_posix(),
                "sha256": sha256(ROOT / path),
                "bytes": (ROOT / path).stat().st_size,
            }
            for path in binaries
        ],
        "python_import_probes": probes,
        "analysis_hashes": freeze["analysis_hashes"],
        "simplepir_commit": subprocess.run(
            ["git", "-C", str(ROOT / "external_pir/simplepir"), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "protected_sentinel_sessions_before_verification": 0,
        "protected_full_sessions": 0,
        "protected_auc_calculations": 0,
    }
    payload["payload_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "repository_commit": head,
                "files": payload["file_count"],
                "binaries": len(payload["binaries"]),
                "module_probes": len(probes),
                "payload_sha256": payload["payload_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

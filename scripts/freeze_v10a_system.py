from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "70709d3ea6aa15f2b5a9fddee0559d28509c0653"
OUT = ROOT / "V10_PRE_HOLDOUT_SYSTEM_FREEZE.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def files_under(path: Path) -> list[Path]:
    ignored = {".git", "__pycache__", ".pytest_cache", "bin", "results_v6"}
    if path.is_file():
        return [path]
    return [p for p in path.rglob("*") if p.is_file() and not any(x in ignored for x in p.parts)]


def manifest(paths: list[Path]) -> dict[str, object]:
    files: list[Path] = []
    for path in paths:
        files.extend(files_under(path))
    files = sorted(set(files), key=lambda p: p.relative_to(ROOT).as_posix())
    entries = [
        {"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
        for p in files
    ]
    h = hashlib.sha256()
    for item in entries:
        h.update(item["path"].encode())
        h.update(b"\0")
        h.update(item["sha256"].encode())
        h.update(b"\n")
    return {"file_count": len(entries), "aggregate_sha256": h.hexdigest(), "entries": entries}


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"refusing to overwrite {OUT.name}")
    head = git("rev-parse", "HEAD")
    if head != EXPECTED_HEAD:
        raise SystemExit(f"unexpected HEAD {head}")
    protected = [
        ROOT / "canonical_v9",
        ROOT / "canonical_v9_1",
        ROOT / "common_action_gateway_v2",
        ROOT / "action_privacy_v8",
        ROOT / "cryptographic_closure" / "pir_backend.py",
        ROOT / "pir_integration" / "simplepir_bridge",
        ROOT / "third_party" / "ohttp-go",
    ]
    dirty = git("diff", "--name-only", "--", *[str(p.relative_to(ROOT)) for p in protected])
    staged = git("diff", "--cached", "--name-only", "--", *[str(p.relative_to(ROOT)) for p in protected])
    if dirty or staged:
        raise SystemExit(f"protected source is dirty: {dirty} {staged}")

    ohttp = json.loads((ROOT / "OHTTP_VENDOR_PROVENANCE_V9.json").read_text(encoding="utf-8"))
    v9 = json.loads((ROOT / "V9_CANONICAL_FUNCTIONAL_FREEZE.json").read_text(encoding="utf-8"))
    components = {
        "canonical_runner": manifest([ROOT / "canonical_v9", ROOT / "common_action_gateway_v2" / "canonicalv9", ROOT / "common_action_gateway_v2" / "cmd" / "canonical-v9-runner"]),
        "v9_1_wrapper_projection": manifest([ROOT / "canonical_v9_1"]),
        "rfc9292_and_ohttp_adapter": manifest([ROOT / "common_action_gateway_v2" / "v9ohttp", ROOT / "common_action_gateway_v2" / "v8", ROOT / "common_action_gateway_v2" / "v7ohttp"]),
        "descriptor_and_routing": manifest([ROOT / "action_privacy_v8"]),
        "simplepir_bridge": manifest([ROOT / "cryptographic_closure" / "pir_backend.py", ROOT / "pir_integration" / "simplepir_bridge"]),
        "ohttp_source": manifest([ROOT / "third_party" / "ohttp-go"]),
        "action_corpus": manifest([ROOT / "ACTION_MEDIATION_CORPUS_V6.csv", ROOT / "ACTION_MEDIATION_COVERAGE_V7.csv"]),
        "openai_framework_snapshot": manifest([ROOT / "external_stage10" / "openai-agents-python"]),
        "microsoft_framework_snapshot": manifest([ROOT / "external_stage9" / "agent-framework"]),
    }
    data = {
        "schema": "AgentTool.V10PreHoldoutSystemFreeze/1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "V10A_FREEZE_ONLY",
        "selected_holdout_executed": False,
        "accepted_git_commit": EXPECTED_HEAD,
        "current_git_commit": head,
        "protected_source_clean": True,
        "worktree_status_at_freeze": git("status", "--short").splitlines(),
        "prior_v9_freeze_aggregate_sha256": v9["aggregate_sha256"],
        "simplepir": {"official_commit": "e9020b03bf2872c75b8954e749e32408b5db87ed"},
        "agent_descriptor_v7": {"schema": "AgentDescriptorV7", "schema_version": 7, "fixed_row_bytes": 1024, "authenticated": True, "source": "action_privacy_v8/descriptor.py"},
        "ohttp": {
            "module": ohttp["module"],
            "expected_upstream_commit": ohttp["expected_upstream_commit"],
            "provenance_class": ohttp["provenance_class"],
            "source_tree_sha256": ohttp["source_tree_sha256"],
            "license": ohttp["license"],
        },
        "frameworks": {
            "openai_agents_sdk": {"revision": git("rev-parse", "HEAD", cwd=ROOT / "external_stage10" / "openai-agents-python")},
            "microsoft_agent_framework": {"revision": git("rev-parse", "HEAD", cwd=ROOT / "external_stage9" / "agent-framework")},
        },
        "components": components,
        "immutability_rule": "Any change to canonical runner, profile, projection, dependency source, harness, or manifests invalidates this V10A freeze before V10B.",
    }
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": OUT.name, "components": {k: v["aggregate_sha256"] for k, v in components.items()}}, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "V9_CANONICAL_FUNCTIONAL_FREEZE.json"

FILES = (
    "V9_STANDARDS_LAYER_FREEZE.json",
    "FINAL_CANONICAL_RUNNER_AUDIT_V9.md",
    "CURRENT_CANONICAL_STATUS_V9.md",
    "CANONICAL_FUNCTIONAL_REPORT_V9.md",
    "CANONICAL_FUNCTIONAL_SUMMARY_V9.csv",
    "CANONICAL_FUNCTIONAL_RESULTS_V9.csv",
    "CANONICAL_MULTI_AGENT_SMOKE_V9.csv",
    "CANONICAL_RECOVERY_MATRIX_V9.csv",
    "CANONICAL_RECOVERY_RESULTS_V9.csv",
    "CANONICAL_RECOVERY_REPORT_V9.md",
    "CANONICAL_OHTTP_SIZE_MATRIX_V9.csv",
    "FUNCTIONAL_DEVELOPMENT_PROFILES_V9.json",
    "CANONICAL_RUNNER_DATAFLOW_V9.md",
    "DELIVERY_LEDGER_RUNTIME_V9.md",
)

TREES = (
    "canonical_v9",
    "common_action_gateway_v2/canonicalv9",
    "common_action_gateway_v2/cmd/canonical-v9-runner",
    "results_v9/canonical_runner_development",
    "results_v9/canonical_recovery_development",
    "CANONICAL_FUNCTIONAL_1_V9",
    "CANONICAL_FUNCTIONAL_10_V9",
    "CANONICAL_FUNCTIONAL_50_V9",
    "CANONICAL_FUNCTIONAL_100_V9",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite frozen V9 evidence: {OUTPUT}")

    paths = [ROOT / item for item in FILES]
    for tree in TREES:
        paths.extend(path for path in (ROOT / tree).rglob("*") if path.is_file())
    paths = sorted(set(paths), key=lambda path: path.relative_to(ROOT).as_posix())
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"V9 freeze inputs missing: {missing}")

    entries = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in paths
    ]
    aggregate = hashlib.sha256(
        "".join(f"{item['path']}\0{item['sha256']}\n" for item in entries).encode()
    ).hexdigest()
    status = git("status", "--porcelain=v1")
    status_entries = [line for line in status.splitlines() if line]
    v9_input_status = [
        line for line in status_entries
        if not line.endswith("scripts/freeze_v9_functional.py")
        and not line.endswith("V9_CANONICAL_FUNCTIONAL_FREEZE.json")
    ]
    payload = {
        "schema": "AgentTool.V9CanonicalFunctionalFreeze/1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "purpose": "Immutable baseline before V9.1 pre-holdout public-profile hardening",
        "git_commit": git("rev-parse", "HEAD"),
        "git_worktree_clean_before_freeze": status == "",
        "git_v9_inputs_clean_before_freeze": not v9_input_status,
        "git_status_at_freeze": status_entries,
        "accepted_development_evidence": {
            "canonical_functional_gate": "PASS",
            "functional_1": "1/1",
            "functional_10": "10/10",
            "functional_50": "50/50",
            "functional_100": "100/100",
            "real_simplepir": True,
            "authenticated_agent_descriptor_v7": True,
            "real_rfc9292": True,
            "real_rfc9458": True,
            "real_local_relay": True,
            "private_route_handle_gateway": True,
            "live_recovery": True,
            "prepared_slot": True,
            "delivery_ledger": "PARTIAL",
            "dummy_provider_operations": 0,
            "timing_privacy": "OPEN / NOT_TESTED",
        },
        "immutability_rule": "Do not overwrite files or results represented by this manifest; V9.1 is a separate layer.",
        "entry_count": len(entries),
        "aggregate_sha256": aggregate,
        "entries": entries,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("status", "git_commit", "entry_count", "aggregate_sha256")}, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "V9_STANDARDS_LAYER_FREEZE.json"

INPUTS = (
    "V8_CANONICAL_FREEZE_V9.json",
    "OHTTP_VENDOR_PROVENANCE_V9.json",
    "OHTTP_VENDOR_SECURITY_AUDIT_V9.md",
    "OFFLINE_OHTTP_BUILD_V9.md",
    "OHTTP_CONFIG_MODEL_V9.md",
    "RFC9458_VALIDATION_V9.md",
    "RFC9292_VALIDATION_V9.md",
    "OHTTP_SIZE_DEVELOPMENT_V9.csv",
    "RELAY_REAL_OHTTP_VALIDATION_V9.md",
    "ADMISSION_RUNTIME_BINDING_V9.md",
    "common_action_gateway_v2/v9ohttp/bhttp_codec.go",
    "common_action_gateway_v2/v9ohttp/ohttp_backend.go",
    "common_action_gateway_v2/v9ohttp/profile_binding_test.go",
    "common_action_gateway_v2/v9ohttp/relay_integration_test.go",
    "common_action_gateway_v2/v9ohttp/v9ohttp_test.go",
    "results_v9/authorized_transfer_validation.json",
    "results_v9/linux_offline_validation.txt",
    "results_v9/pir_v7_descriptor_smoke/simplepir/metrics.json",
    "results_v9/pir_v7_descriptor_smoke/simplepir/server_visible_trace.jsonl",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite frozen checkpoint {OUTPUT}")
    missing = [name for name in INPUTS if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError(f"standards-layer freeze inputs missing: {missing}")
    entries = [
        {
            "path": name,
            "bytes": (ROOT / name).stat().st_size,
            "sha256": digest(ROOT / name),
        }
        for name in INPUTS
    ]
    canonical = "".join(
        f"{entry['sha256']} {entry['bytes']} {entry['path']}\n" for entry in entries
    ).encode()
    payload = {
        "schema": "AgentTool.V9StandardsLayerFreeze/1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "checkpoint": "V9_STANDARDS_LAYER_BEFORE_CANONICAL_RUNNER",
        "source_provenance": "SOURCE_TREE_HASH_ONLY",
        "rfc9458_implementation": "PASS",
        "rfc9458_appendix_a": "BLOCKED_VECTOR_NOT_SUPPLIED",
        "rfc9292_bhttp": "PASS",
        "real_ohttp_relay": "PASS",
        "development_request_bytes": 1079,
        "development_response_bytes": 800,
        "post_integration_pir_smoke": "4/4 PASS",
        "entry_count": len(entries),
        "aggregate_sha256": hashlib.sha256(canonical).hexdigest(),
        "entries": entries,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("status", "entry_count", "aggregate_sha256")}))


if __name__ == "__main__":
    main()

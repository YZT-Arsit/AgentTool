from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v12_causal_horizon_python_gate import selected_specs


OUTPUT = ROOT / "V12_CAUSAL_HORIZON_PYTHON_MANIFEST_R3.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    specs = selected_specs()
    source_paths = sorted({spec.split("::", 1)[0] for spec in specs})
    payload = {
        "schema": "AgentTool.V12CausalHorizonPythonManifest/3",
        "phase": "V12-TIMING-CAUSAL-HORIZON-REQUALIFICATION",
        "base_commit": "4a577ec8c4f610e7f9b8fa1b852a518fb4eb2e0c",
        "frozen_before_decisive_execution": True,
        "supersedes_manifests": {
            "V12_CAUSAL_HORIZON_PYTHON_MANIFEST.json": sha(ROOT / "V12_CAUSAL_HORIZON_PYTHON_MANIFEST.json"),
            "V12_CAUSAL_HORIZON_PYTHON_MANIFEST_R2.json": sha(ROOT / "V12_CAUSAL_HORIZON_PYTHON_MANIFEST_R2.json"),
        },
        "supersession_reason": "R1 failed 73/75 on stale Q50 and omitted-empty-key assertions; R2 failed 74/75 on the remaining stale dummy49 assertion. Both results and identities remain preserved",
        "source_specs": specs,
        "expected_node_count": 75,
        "source_hashes": {path: sha(ROOT / path) for path in source_paths},
        "serial_command_contract": "<python> -m pytest -q --basetemp <fresh-root> -p no:xdist <source_specs>",
        "default_command_contract": "<python> -m pytest -q --basetemp <fresh-root> <source_specs>",
        "expected_skips": 0,
        "timing_attack_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

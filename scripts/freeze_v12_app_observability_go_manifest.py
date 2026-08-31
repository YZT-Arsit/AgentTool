from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "V12_APPLICATION_OBSERVABILITY_GO_MANIFEST.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def names(relative: str) -> list[str]:
    result = []
    for path in sorted((ROOT / relative).glob("*_test.go")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("func Test"):
                result.append(line.split("(", 1)[0].split()[1])
    return result


def main() -> int:
    prior = json.loads((ROOT / "V12_CAUSAL_HORIZON_GO_MANIFEST_R3.json").read_text(encoding="utf-8"))
    canonical = list(prior["packages"]["common-action-gateway-v2/canonicalv9"])
    canonical.extend(["TestV12V3EffectiveClockRecurrenceAcrossFrozenDeltas", "TestV12V3ProfileRevisionBinding"])
    packages = {
        "common-action-gateway-v2": prior["packages"]["common-action-gateway-v2"],
        "common-action-gateway-v2/canonicalv9": canonical,
        "common-action-gateway-v2/v7": names("common_action_gateway_v2/v7"),
        "common-action-gateway-v2/v7ohttp": names("common_action_gateway_v2/v7ohttp"),
        "common-action-gateway-v2/v8": names("common_action_gateway_v2/v8"),
        "common-action-gateway-v2/v9ohttp": names("common_action_gateway_v2/v9ohttp"),
    }
    count = sum(len(value) for value in packages.values())
    payload = {
        "schema": "AgentTool.V12ApplicationObservabilityGoManifest/1",
        "revision": 2,
        "supersedes_preliminary_manifest_sha256": "95b66781fec35e057815a951127d38a4c97bc6959fa1b47e873845c58aa5a2bb6",
        "preliminary_gate_disposition": "FAILED_TEST_FIXTURE_PRESERVED",
        "frozen_before_full_affected_gate": True,
        "frozen_before_decisive_rerun": True,
        "inherits": "V12_CAUSAL_HORIZON_GO_MANIFEST_R3.json",
        "inherits_sha256": sha(ROOT / "V12_CAUSAL_HORIZON_GO_MANIFEST_R3.json"),
        "packages": packages, "test_count": count,
        "simplepir_bridge_tests": ["TestApplicationResponseSendBoundaryIsContentIndependent"],
        "simplepir_bridge_test_count": 1,
        "total_go_tests": count + 1,
        "source_hashes": {path: sha(ROOT / path) for path in (
            "common_action_gateway_v2/v8/http_relay.go", "common_action_gateway_v2/v8/v8_test.go",
            "common_action_gateway_v2/canonicalv9/runner.go", "common_action_gateway_v2/canonicalv9/canonicalv9_test.go",
            "pir_integration/simplepir_bridge/main.go", "pir_integration/simplepir_bridge/main_test.go")},
        "classifier_training_runs": 0, "real_auc_calculations": 0,
    }
    payload["payload_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

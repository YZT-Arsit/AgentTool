from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "V12_CAUSAL_HORIZON_GO_MANIFEST_R3.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def go_test_names(relative: str) -> list[str]:
    names: list[str] = []
    for path in sorted((ROOT / relative).glob("*_test.go")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("func Test"):
                names.append(line.split("(", 1)[0].split()[1])
    return names


def main() -> int:
    prior = json.loads((ROOT / "V12_NON_TIMING_GO_MANIFEST.json").read_text(encoding="utf-8"))
    canonical = list(prior["packages"]["common-action-gateway-v2/canonicalv9"])
    canonical.extend(
        [
            "TestV12TimingProfileEmitsEverySlotAfterThirtyFiveMillisecondDelay",
            "TestV12EffectivePublicClockStateMachine",
            "TestV12EffectivePublicClockRejectsAfterEffectiveCutoff",
            "TestV12EffectiveClockDependsOnlyOnPublicDispatch",
            "TestV12ResultEligibilityUsesFrozenEffectiveCutoff",
            "TestV12TimingProfilePreservesTranscriptAfterHundredMillisecondDelay",
            "TestV12TimingSemanticErrorDoesNotTruncatePublicCover",
            "TestV12TimingNoDropNoBurstRecoveryIsPublicAndComplete",
        ]
    )
    payload = {
        "schema": "AgentTool.V12CausalHorizonGoManifest/3",
        "phase": "V12-TIMING-CAUSAL-HORIZON-REQUALIFICATION",
        "frozen_before_decisive_current_affected_gate": True,
        "supersedes_manifests": {
            "V12_CAUSAL_HORIZON_GO_MANIFEST.json": sha(ROOT / "V12_CAUSAL_HORIZON_GO_MANIFEST.json"),
            "V12_CAUSAL_HORIZON_GO_MANIFEST_R2.json": sha(ROOT / "V12_CAUSAL_HORIZON_GO_MANIFEST_R2.json"),
        },
        "supersession_reason": "R1 violated a prior exact historical-timing exclusion; R2 preserved stale ALL_N package denominators. Both manifests and failed harness outcomes remain preserved",
        "inherits_non_timing_manifest": "V12_NON_TIMING_GO_MANIFEST.json",
        "inherits_non_timing_manifest_sha256": sha(ROOT / "V12_NON_TIMING_GO_MANIFEST.json"),
        "packages": {
            "common-action-gateway-v2": prior["packages"]["common-action-gateway-v2"],
            "common-action-gateway-v2/canonicalv9": canonical,
            "common-action-gateway-v2/v7": go_test_names("common_action_gateway_v2/v7"),
            "common-action-gateway-v2/v7ohttp": go_test_names("common_action_gateway_v2/v7ohttp"),
            "common-action-gateway-v2/v8": go_test_names("common_action_gateway_v2/v8"),
            "common-action-gateway-v2/v9ohttp": go_test_names("common_action_gateway_v2/v9ohttp"),
        },
        "test_count": 79,
        "source_hashes": {
            "common_action_gateway_v2/canonicalv9/online.go": sha(ROOT / "common_action_gateway_v2/canonicalv9/online.go"),
            "common_action_gateway_v2/canonicalv9/runner.go": sha(ROOT / "common_action_gateway_v2/canonicalv9/runner.go"),
            "common_action_gateway_v2/canonicalv9/canonicalv9_test.go": sha(ROOT / "common_action_gateway_v2/canonicalv9/canonicalv9_test.go"),
            "common_action_gateway_v2/canonicalv9/pacer_test.go": sha(ROOT / "common_action_gateway_v2/canonicalv9/pacer_test.go"),
            "common_action_gateway_v2/v7/ready_queue.go": sha(ROOT / "common_action_gateway_v2/v7/ready_queue.go"),
        },
        "historical_timing_tests_excluded_by_prior_frozen_manifest": [
            {
                "node": "canonicalv9/TestV11_2OnlineCausalActionsUseOnePreconnectedSession",
                "reason": "historical V11 5-ms timing profile; exact exclusion was frozen before this phase",
            },
            {
                "node": "canonicalv9/TestV11_2OnlineSchedulerFailureIsExplicitAndDoesNotRestart",
                "reason": "historical V11 hard-deadline failure semantics; exact exclusion was frozen before this phase",
            },
            {
                "node": "canonicalv9/TestV12_1OnlineSubperiodSlipIsDiagnosticNotScheduleMiss",
                "reason": "historical diagnostic-tolerance profile; exact exclusion was frozen before this phase",
            },
            {
                "node": "canonicalv9/TestV11_2OnlineCapacityRejectsWithoutSecondSession",
                "reason": "historical V11 5-ms timing profile; current V2 M50 capacity is covered by deterministic and live gates",
            },
        ],
        "repository_wide_exploratory_result_is_not_regraded": True,
        "timing_attack_sessions": 0,
        "selected_final_v12_cases_executed": 0,
    }
    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["payload_sha256"] = hashlib.sha256(canonical_bytes).hexdigest()
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

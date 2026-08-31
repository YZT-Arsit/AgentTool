from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v12_timing.matrix import TASKS, frozen_order, workflow_manifest


SEED = "f60c4650077a822f1022623f2a9391bdd49789f8d53d17f3cb979b75bafff8d5"
BLOCKS = 50


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    rows: list[dict[str, object]] = []
    for period in (10, 20, 25):
        rows.extend(workflow_manifest(item) | {"nominal_delta_ms": period, "pir_period_ms": 60} for item in frozen_order(profile_period=period, blocks=BLOCKS, seed_hex=SEED))
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    freeze = {
        "schema": "AgentTool.V12TimingDevelopmentMatrix/1",
        "phase": "V12-TIMING-INDISTINGUISHABILITY-CLOSURE",
        "base_commit": "ca6a79a92f3c6730f0909e015de1c6db722ac812",
        "seed_search": False,
        "randomization_seed_sha256": SEED,
        "seed_derivation": "SHA256(exact threat-model bytes || observer-projection bytes || candidate-profile-freeze bytes || PIR-path-audit bytes || AgentTool-V12-timing-development-matrix-v1)",
        "public_periods_ms": [10, 20, 25],
        "pir_period_ms": 60,
        "pir_period_selection_rule": "test 60 first; test 75 only if 60 fails functional fixed-cover qualification; test 100 only if both smaller candidates fail; never search or add candidates",
        "tasks": TASKS,
        "orthogonal_design": "16-row Walsh-Hadamard columns 1..10; every factor is balanced and each factor pair is orthogonal in every complete block",
        "blocks_per_profile": BLOCKS,
        "sessions_per_class_per_task_per_profile": 8 * BLOCKS,
        "sessions_per_task_per_profile": 16 * BLOCKS,
        "sessions_per_profile": 16 * BLOCKS,
        "total_sessions": len(rows),
        "block_rule": "each 16-session block contains the complete orthogonal design; row order is independently shuffled inside each block",
        "statistical_unit": "one session/workflow",
        "outlier_removal": "PROHIBITED",
        "retry": "PROHIBITED",
        "capacity_gate_identities": [f"DEV-TD-CAPACITY50-P{period}-PIR60" for period in (10, 20, 25)],
        "workflow_manifest_sha256": hashlib.sha256(canonical).hexdigest(),
        "generator_sha256": _sha(ROOT / "v12_timing" / "matrix.py"),
        "workflows": rows,
    }
    path = ROOT / "V12_TIMING_DEVELOPMENT_MATRIX.json"
    path.write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8", newline="\n")
    protocol = {
        "schema": "AgentTool.V12TimingDevelopmentProtocol/1",
        "matrix_sha256": _sha(path),
        "profiles": [
            {"delta_ms": 10, "pir_period_ms": 60},
            {"delta_ms": 20, "pir_period_ms": 60},
            {"delta_ms": 25, "pir_period_ms": 60},
        ],
        "profile_execution_order": [10, 20, 25],
        "functional_gate": {
            "native_canonical_level_a_projection_equal": True,
            "causal_proof": "PASS",
            "public_transcript_complete": True,
            "exact_authenticated_slot_order": True,
            "fixed_request_bytes": 1079,
            "fixed_response_bytes": 800,
            "duplicate_slots": 0,
            "missing_slots": 0,
            "dummy_provider_operations": 0,
            "profile_overflow_events": 0,
            "silent_committed_result_losses": 0,
            "infrastructure_liveness_failures": 0,
        },
        "development_attack_screen": {
            "models": ["LOGISTIC_REGRESSION", "EXTRA_TREES", "HIST_GRADIENT_BOOSTING", "RBF_SVM"],
            "cross_validation": "5-fold stratified-group by randomized block",
            "bootstrap_resamples": 10000,
            "protected_rule": "best-attacker upper 95% session-bootstrap AUC <= 0.55",
            "positive_control_rule": "best-attacker lower 95% session-bootstrap AUC >= 0.60",
            "all_tasks_and_both_observers_required": True,
        },
        "selection_rule": "smallest Delta satisfying functional full transcript and development attack rules; all three candidates are nevertheless executed and reported",
        "first_decisive_failure": "preserve and stop without retry",
        "selected_final_v12_holdout": False,
    }
    (ROOT / "V12_TIMING_DEVELOPMENT_PROTOCOL.json").write_text(
        json.dumps(protocol, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()

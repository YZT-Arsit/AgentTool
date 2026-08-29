from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_3.profile import candidate_profiles


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    preserved = [
        "FINAL_ONLINE_TRAJECTORY_AUDIT_V11_2.md",
        "ONLINE_RELIABILITY_STRESS_V11_2.md",
        "ONLINE_DEVELOPMENT_FAILURES_V11_2.md",
        "ONLINE_CAUSAL_WORKFLOWS_V11_2.csv",
        "ONLINE_SEMANTIC_DEVELOPMENT_V11_2.csv",
        "ONLINE_STRUCTURAL_REGRESSION_V11_2.csv",
        "results_v11_2_development/linux_campaign_d/same_config_prefreeze_smoke_failure.json",
        "results_v11_2_development/linux_campaign_d/online_reliability_stress.csv",
        "results_v11_2_development/linux_campaign_d/raw_evidence_sha256.txt",
    ]
    for relative in preserved:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(relative)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    freeze = {
        "schema": "AgentTool.V11_2OnlineDevelopmentFreezeForV11_3/1",
        "source_commit": head,
        "immutable_evidence": {relative: sha256(ROOT / relative) for relative in preserved},
        "accepted": {
            "online_dynamic_action_ingress": "PASS",
            "single_public_session": "PASS",
            "live_result_delivery": "PASS",
            "dynamic_simplepir": "PASS",
            "online_agent_as_tool": "PASS",
            "online_openai_handoff": "PASS",
            "causal_workflows": "6/6",
            "semantic_regression": "8/8",
            "structural_size_regression": "5/5",
            "campaign_d": "380/380",
            "session_count_audit": "404/404 exactly one session",
            "dummy_heavy_operations": 0,
            "scheduler_miss": 0,
            "profile_overflow": 0,
            "silent_committed_result_loss": 0,
        },
        "preserved_negative": {
            "same_configuration_prefreeze": "17/20",
            "profile_admission_closed": 3,
            "failure_point": "tenth causal action after H50 admission closure",
            "relabelled": False,
        },
        "old_v10_selected_outcomes_observed": False,
        "v10_1_selected_outcomes_observed": False,
    }
    write_json(ROOT / "V11_2_ONLINE_DEVELOPMENT_FREEZE_V11_3.json", freeze)

    candidates = {
        "schema": "AgentTool.V11_3OnlineProfileCandidates/1",
        "frozen_before_qualification": True,
        "vary_only": "admission_rounds",
        "fixed": {
            "maximum_real_operations": 50,
            "round_period_ms": 5,
            "provider_completion_bound_ms": 50,
            "completion_rounds": 10,
            "result_drain_rounds": 50,
            "terminal_rounds": 1,
            "request_final_bytes": 1079,
            "response_final_bytes": 800,
            "session_count": 1,
            "connection_policy": "ONE_PERSISTENT_KEEP_ALIVE_CONNECTION_PER_PUBLIC_SESSION",
            "ohttp_suite": {"key_id": 7, "kem_id": 32, "kdf_id": 1, "aead_id": 1, "config_epoch": 3},
        },
        "selection_rule": "choose the smallest candidate that passes every predeclared development qualification gate; stop without running larger candidates",
        "seed_search": False,
        "candidates": [profile.public_schema() for profile in candidate_profiles()],
        "holdout_selected_or_executed": False,
    }
    write_json(ROOT / "ONLINE_PROFILE_CANDIDATES_V11_3.json", candidates)

    (ROOT / "ONLINE_ADMISSION_ROOT_CAUSE_V11_3.md").write_text(
        "# V11.3 online admission root cause\n\n"
        "The preserved V11.2 H50 profile used `M=50`, `A=50`, and `Delta=5 ms`, so its public admission horizon was only `A*Delta=250 ms`. That coupling came from the static/predeclared workload design. In an online causal trajectory, the maximum count of real operations and the number of public opportunities in which future operations may become ready are distinct public parameters. Three of 20 same-configuration V11.2 sessions therefore failed closed before the tenth action with `PROFILE_ADMISSION_CLOSED`.\n\n"
        "Classification: `ONLINE_PROFILE_ADMISSION_HORIZON_TOO_SHORT`. This is not classified as scheduler, SimplePIR, OHTTP, or trajectory-privacy failure. The 17/20 result and all three failures remain immutable negative evidence.\n",
        encoding="utf-8",
    )
    (ROOT / "ONLINE_PROFILE_MODEL_V11_3.md").write_text(
        "# V11.3 online public-profile model\n\n"
        "The public profile separates `M` (maximum admitted real operations), `A` (admission rounds), `Delta` (round period), `B_provider` (declared provider completion bound), `C=ceil(B_provider/Delta)`, result-drain capacity `D`, terminal rounds `T`, and total rounds `R`. The conservative one-result-per-response-slot rule is `R = A + C + M + T`. V11.3 fixes `M=50`, `Delta=5 ms`, `B_provider=50 ms`, `C=10`, `D=M=50`, and `T=1`; only `A` varies across the predeclared development candidates.\n\n"
        "`maximum_real_operations=50` means at most 50 real actions can be admitted while the fixed public admission horizon is open. It does not mean admission is limited to the first 50 rounds. Empty admission and drain-only request slots carry encrypted NOOP; every response slot carries one fixed-size result or WAIT frame. A fixed profile does not promise progress for an arbitrarily slow framework. An action ready after the public admission horizon is rejected privately without extending slots, lifetime, connections, or sessions.\n",
        encoding="utf-8",
    )
    (ROOT / "ONLINE_PROFILE_SELECTION_V11_3.md").write_text(
        "# V11.3 profile selection rule (predeclared)\n\n"
        "Candidates are evaluated in order `A = 75, 100, 150, 200, 300`. For each candidate the main strictly causal gate contains 100 ten-action, 50 twenty-action, 30 thirty-action, and 20 fifty-action independent non-holdout development sessions. A candidate passes only if every required run is functional and has no admission closure, schedule miss, transport failure, overflow, silent committed-result loss, unresolved waiter, missing result, duplicate framework result, or dummy heavy operation, while preserving exactly one session, `R` rounds, 1079/800-byte messages, two single reused HTTP/2 hops, the frozen OHTTP suite, and scheduled lifetime `R*5 ms`.\n\n"
        "The selected profile is the first and smallest candidate passing all gates. If a candidate fails, qualification proceeds to the next predeclared candidate. Once one passes, larger candidates are not executed. Candidate values, selection rule, and statistics are frozen before qualification; there is no seed search and no holdout inspection.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

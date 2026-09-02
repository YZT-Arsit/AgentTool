from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from typing import Any

from . import sentinel_smoke as _base
from .isolated_tasks import PrimaryTimingWorkload, build_primary_workload
from .profile import duplex_response_anchor_p10_profile

BASE_ATTRIBUTION = "eedc1cfb55973ec8885a971129353c9211111aea"
BASE_V4R7_SMOKE = "f66649590f1159a5bce280baaea2cfdc3218435c"
BASE_UTILITY_CLOSURE = "06bb4677fe51defb8823a1fcaf685856cda15845"
HISTORICAL_P10_RESULT_SHA = "558c97bd5ca8bb9123382800cb73eb410cab6342"
SMOKE_SEED_LABEL = "V12-V4R8-RESPONSE-PUBLIC-ANCHOR-REPAIR-SMOKE-20260902"
WORKLOAD_BLOCK_OFFSET = 60_000

PLANNED_BLOCKS = _base.PLANNED_BLOCKS
PLANNED_TRAIN_BLOCKS = _base.PLANNED_TRAIN_BLOCKS
PLANNED_EVAL_BLOCKS = _base.PLANNED_EVAL_BLOCKS
TARGET_TRAIN_COMPLETE_BLOCKS = _base.TARGET_TRAIN_COMPLETE_BLOCKS
TARGET_EVAL_COMPLETE_BLOCKS = _base.TARGET_EVAL_COMPLETE_BLOCKS
SESSIONS_PER_COORDINATE = _base.SESSIONS_PER_COORDINATE
TOTAL_SESSIONS = _base.TOTAL_SESSIONS
SMOKE_LCB_QUANTILE = _base.SMOKE_LCB_QUANTILE
SMOKE_FAILURE_MARGIN = _base.SMOKE_FAILURE_MARGIN
BOOTSTRAP_RESAMPLES = _base.BOOTSTRAP_RESAMPLES
RANDOMIZATION_RESAMPLES = _base.RANDOMIZATION_RESAMPLES

physical_coordinates = _base.physical_coordinates
completion_channel = _base.completion_channel
select_complete_blocks = _base.select_complete_blocks


def p10_profile():
    profile = duplex_response_anchor_p10_profile()
    if profile.total_rounds != 521:
        raise AssertionError("V4R8 response-anchor smoke P10 profile drifted")
    return profile


def build_smoke_workload(
    task_id: str, framework: str, label: int, *, planned_block: int
) -> PrimaryTimingWorkload:
    if not 0 <= planned_block < PLANNED_BLOCKS:
        raise ValueError("V4R8 smoke block is outside the frozen denominator")
    return build_primary_workload(
        task_id,
        framework,
        label,
        block=WORKLOAD_BLOCK_OFFSET + planned_block,
        stage="SENTINEL",
        delta_ms=10,
    )


@contextmanager
def _configuration():
    replacements = {
        "BASE_COST_ABORT_COMMIT": BASE_ATTRIBUTION,
        "BASE_DUPLEX_EVIDENCE": BASE_UTILITY_CLOSURE,
        "HISTORICAL_P10_RESULT_SHA": HISTORICAL_P10_RESULT_SHA,
        "SMOKE_SEED_LABEL": SMOKE_SEED_LABEL,
        "WORKLOAD_BLOCK_OFFSET": WORKLOAD_BLOCK_OFFSET,
        "p10_profile": p10_profile,
        "build_smoke_workload": build_smoke_workload,
    }
    previous = {name: getattr(_base, name) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(_base, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(_base, name, value)


def build_freeze_manifest(**kwargs: Any) -> dict[str, Any]:
    with _configuration():
        manifest = _base.build_freeze_manifest(**kwargs)
    manifest["schema"] = "AgentTool.V12V4R8ResponseAnchorSmokeFreeze/1"
    manifest["phase"] = "V12-V4R8-RESPONSE-PUBLIC-ANCHOR-REPAIR"
    manifest["base_attribution"] = manifest.pop("base_cost_abort_commit")
    manifest["base_utility_closure"] = manifest.pop("base_duplex_evidence")
    manifest["base_v4r7_smoke"] = BASE_V4R7_SMOKE
    manifest["runtime_revision"] = "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R8"
    manifest["targeted_change"] = (
        "REMOVE_GATEWAY_REQUEST_ARRIVAL_FROM_PLANNED_RESPONSE_CLOCK"
    )
    manifest["response_clock"] = {
        "old": "F_i=max(E_i+rho,gateway_request_arrival_i+L_response,F_(i-1)+Delta)",
        "new": "F_1=E_1+rho; F_i=max(E_i+rho,F_(i-1)+Delta)",
        "gateway_arrival_in_F_i": False,
        "commitment_cutoff": "G_i=F_i-L_response",
        "physical_release": "S_i=max(F_i,S_(i-1)+Delta)",
    }
    manifest["closed_utility_work_reexecuted"] = False
    manifest["collector_integrity_contract"] = {
        "deadline_slip": "DIAGNOSTIC_ONLY",
        "missing_or_duplicate_slot": "COMMON_INTEGRITY_FAILURE",
        "failed_response_write": "COMMON_INTEGRITY_FAILURE",
        "no_catch_up_violation": "COMMON_INTEGRITY_FAILURE",
    }
    manifest.pop("payload_sha256", None)
    manifest["payload_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    validate_freeze_manifest(manifest, excluded_identities=kwargs["excluded_identities"])
    return manifest


def validate_freeze_manifest(manifest: Any, *, excluded_identities: Any = ()) -> None:
    payload = dict(manifest)
    claimed = str(payload.pop("payload_sha256", ""))
    actual = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if claimed != actual:
        raise ValueError("V4R8 smoke manifest payload hash drifted")
    if manifest["schema"] != "AgentTool.V12V4R8ResponseAnchorSmokeFreeze/1":
        raise ValueError("wrong V4R8 smoke manifest schema")
    if manifest["base_attribution"] != BASE_ATTRIBUTION:
        raise ValueError("V4R8 attribution base drifted")
    if manifest["base_v4r7_smoke"] != BASE_V4R7_SMOKE:
        raise ValueError("V4R8 smoke base drifted")
    base_form = dict(manifest)
    base_form["schema"] = "AgentTool.V12DuplexRepairSmokeSentinelFreeze/1"
    base_form["phase"] = "V12-DUPLEX-REPAIR-SMOKE-SENTINEL"
    base_form["base_cost_abort_commit"] = base_form.pop("base_attribution")
    base_form["base_duplex_evidence"] = base_form.pop("base_utility_closure")
    for key in (
        "base_v4r7_smoke",
        "runtime_revision",
        "targeted_change",
        "response_clock",
        "closed_utility_work_reexecuted",
        "collector_integrity_contract",
    ):
        base_form.pop(key, None)
    base_form.pop("payload_sha256", None)
    base_form["payload_sha256"] = hashlib.sha256(
        json.dumps(base_form, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with _configuration():
        _base.validate_freeze_manifest(
            base_form, excluded_identities=excluded_identities
        )
    if manifest["profile"]["profile_id"] != (
        "V12-TIMING-INDIST-V4R8-H50-H4500-P10-B200-PIR60"
    ):
        raise ValueError("V4R8 profile drifted")
    if int(manifest["profile"]["total_rounds"]) != 521:
        raise ValueError("V4R8 smoke R drifted")
    if int(manifest["feature_contract"]["RELAY_feature_width"]) != 5860:
        raise ValueError("V4R8 Relay feature width drifted")
    if manifest["response_clock"]["gateway_arrival_in_F_i"] is not False:
        raise ValueError("Gateway arrival remained in V4R8 F_i")


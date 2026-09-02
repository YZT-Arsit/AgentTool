from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from typing import Any

from . import sentinel_smoke as _base
from .isolated_tasks import PrimaryTimingWorkload, build_primary_workload
from .profile import duplex_provider_bound_p10_profile

BASE_ABORT = "6be7408113583323e6c249c0ab881344b6a61235"
BASE_CONTRACT_CLOSURE = "06bb4677fe51defb8823a1fcaf685856cda15845"
HISTORICAL_P10_RESULT_SHA = "558c97bd5ca8bb9123382800cb73eb410cab6342"
SMOKE_SEED_LABEL = "V12-V4R7-LATE-FRAME-COLLECTOR-SMOKE-20260902"
WORKLOAD_BLOCK_OFFSET = 50_000

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
    profile = duplex_provider_bound_p10_profile()
    if profile.total_rounds != 521:
        raise AssertionError("V4R7 late-frame smoke P10 profile drifted")
    return profile


def build_smoke_workload(
    task_id: str, framework: str, label: int, *, planned_block: int
) -> PrimaryTimingWorkload:
    if not 0 <= planned_block < PLANNED_BLOCKS:
        raise ValueError("late-frame smoke block is outside the frozen denominator")
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
        "BASE_COST_ABORT_COMMIT": BASE_ABORT,
        "BASE_DUPLEX_EVIDENCE": BASE_CONTRACT_CLOSURE,
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
    manifest["schema"] = "AgentTool.V12V4R7LateFrameCollectorSmokeFreeze/1"
    manifest["phase"] = "V12-V4R7-SMOKE-COLLECTOR-LATE-FRAME-CONTRACT-CLOSURE"
    manifest["base_abort"] = manifest.pop("base_cost_abort_commit")
    manifest["base_contract_closure"] = manifest.pop("base_duplex_evidence")
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
        raise ValueError("late-frame smoke manifest payload hash drifted")
    if manifest["schema"] != "AgentTool.V12V4R7LateFrameCollectorSmokeFreeze/1":
        raise ValueError("wrong late-frame smoke manifest schema")
    base_form = dict(manifest)
    base_form["schema"] = "AgentTool.V12DuplexRepairSmokeSentinelFreeze/1"
    base_form["phase"] = "V12-DUPLEX-REPAIR-SMOKE-SENTINEL"
    base_form["base_cost_abort_commit"] = base_form.pop("base_abort")
    base_form["base_duplex_evidence"] = base_form.pop("base_contract_closure")
    base_form.pop("collector_integrity_contract", None)
    base_form.pop("payload_sha256", None)
    base_form["payload_sha256"] = hashlib.sha256(
        json.dumps(base_form, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with _configuration():
        _base.validate_freeze_manifest(
            base_form, excluded_identities=excluded_identities
        )
    if int(manifest["profile"]["total_rounds"]) != 521:
        raise ValueError("late-frame smoke R drifted")
    if int(manifest["feature_contract"]["RELAY_feature_width"]) != 5860:
        raise ValueError("late-frame smoke Relay feature width drifted")
    if manifest["collector_integrity_contract"]["deadline_slip"] != "DIAGNOSTIC_ONLY":
        raise ValueError("late-frame diagnostic contract drifted")

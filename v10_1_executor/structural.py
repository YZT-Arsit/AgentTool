from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from action_privacy_v8 import ActionKind, ProtectedActionIntent
from canonical_v9.runner import CanonicalSessionSpec, deliver_results, real_pir_select, resolve_session
from canonical_v9_1.projection import strict_size_projection, strict_structural_projection
from canonical_v9_1.runner import invoke_go_with_public_profile
from v10_holdout.harness import load_v10_profile

from .providers import EvidenceProviders


@dataclass(frozen=True)
class StructuralAction:
    operation_id: str
    capability: str
    action_kind: str
    protected_argument: str


@dataclass(frozen=True)
class StructuralArmSpec:
    arm_id: str
    agent_id: int
    agent_capability: str
    actions: tuple[StructuralAction, ...]


@dataclass(frozen=True)
class StructuralExecutionRecord:
    functional: bool
    raw_trace: dict[str, Any]
    strict_structural_projection: dict[str, Any]
    strict_size_projection: dict[str, Any]
    correctness: dict[str, Any]


def run_structural_arm(arm_spec: StructuralArmSpec, public_profile=None, output: Path | None = None) -> StructuralExecutionRecord:
    """Execute an arm; this function does not know or load holdout manifests."""

    profile = public_profile or load_v10_profile()
    if output is None:
        raise ValueError("structural executor requires an explicit append-only artifact directory")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite structural executor artifacts: {output}")
    kind_map = {"TOOL": ActionKind.TOOL, "AGENT_SERVICE": ActionKind.AGENT_SERVICE, "EXTERNAL_HTTP": ActionKind.EXTERNAL_HTTP}
    intents = tuple(
        ProtectedActionIntent(action.capability, action.protected_argument.encode(), "v10.1-structural-executor", action.operation_id, kind_map[action.action_kind])
        for action in arm_spec.actions
    )
    spec = CanonicalSessionSpec(arm_spec.arm_id, arm_spec.agent_capability, arm_spec.agent_id, intents)
    selected = real_pir_select(output / "pir", [spec])
    resolved = resolve_session(spec, selected[arm_spec.arm_id])
    with EvidenceProviders() as providers:
        trace, schedule = invoke_go_with_public_profile(output / "canonical_session", profile, resolved, providers)
        delivery = deliver_results(output / "delivery", [action.operation_id for action in arm_spec.actions], trace)
        observed = [providers.observed(action.operation_id) for action in arm_spec.actions]
    functional = (
        not delivery["missing"]
        and not delivery["unexpected"]
        and int(trace["provider_invocations"]) == len(arm_spec.actions)
        and int(trace["dummy_provider_operations"]) == 0
        and int(trace["profile_overflow_events"]) == 0
    )
    correctness = {
        "real_simplepir": selected[arm_spec.arm_id].agent_id == arm_spec.agent_id,
        "descriptor_authenticated": True,
        "authorized_routes": [item["route_handle"] for item in resolved],
        "provider_requests": observed,
        "delivery": delivery,
        "public_profile_selected_before_private_execution": schedule["profile_selected_before_private_execution"],
        "dummy_provider_operations": trace["dummy_provider_operations"],
        "profile_overflow_events": trace["profile_overflow_events"],
    }
    return StructuralExecutionRecord(
        functional,
        trace,
        strict_structural_projection(trace, profile),
        strict_size_projection(trace, profile),
        correctness,
    )

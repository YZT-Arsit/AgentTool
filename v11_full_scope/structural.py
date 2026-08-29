from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from action_privacy_v8 import ActionKind, ProtectedActionIntent
from canonical_v9.runner import CanonicalSessionSpec, descriptor, resolve_session

from .canonical import canonical_external_outcome, public_projections
from .models import V11ActionCase, V11ActionOutcome


def canonical_effect_semantics(
    agent_id: int,
    agent_capability: str,
    action_kind: str,
    capability: str,
) -> str:
    kind = {
        "TOOL": ActionKind.TOOL,
        "EXTERNAL_HTTP": ActionKind.EXTERNAL_HTTP,
        "AGENT_SERVICE": ActionKind.AGENT_SERVICE,
    }[action_kind]
    intent = ProtectedActionIntent(capability, b"preexecution", "v11-structural-validation", "validate", kind)
    spec = CanonicalSessionSpec("v11-structural-validation", agent_capability, agent_id, (intent,))
    return str(resolve_session(spec, descriptor(agent_id))[0]["effect_semantics"])


def validate_structural_action(
    agent_id: int,
    agent_capability: str,
    action: Mapping[str, Any],
) -> None:
    expected = canonical_effect_semantics(
        agent_id,
        agent_capability,
        str(action["action_kind"]),
        str(action["capability"]),
    )
    if action["effect_semantics"] != expected:
        raise ValueError(
            f"structural effect semantics mismatch: manifest={action['effect_semantics']} canonical={expected}"
        )


@dataclass(frozen=True)
class DevelopmentStructuralPairResult:
    functional: bool
    structural_equal: bool
    size_equal: bool
    arm_a: V11ActionOutcome
    arm_b: V11ActionOutcome


def run_development_pair(
    arm_a: V11ActionCase,
    arm_b: V11ActionCase,
    output: Path,
) -> DevelopmentStructuralPairResult:
    if output.exists():
        raise FileExistsError("refusing to overwrite V11 structural development evidence")
    a = canonical_external_outcome(arm_a, output / "A")
    b = canonical_external_outcome(arm_b, output / "B")
    a_struct, a_size = public_projections(a)
    b_struct, b_size = public_projections(b)
    functional = bool(a.result) and bool(b.result)
    return DevelopmentStructuralPairResult(
        functional,
        a_struct == b_struct,
        a_size == b_size,
        a,
        b,
    )

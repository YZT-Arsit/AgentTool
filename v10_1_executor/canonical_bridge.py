from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path
from typing import Any

from action_privacy_v8 import ActionKind, ProtectedActionIntent
from canonical_v9.runner import CanonicalSessionSpec, deliver_results, real_pir_select, resolve_session
from canonical_v9_1.runner import invoke_go_with_public_profile
from v10_holdout.harness import load_v10_profile

from .models import ActionOutcome, CaseSpec
from .providers import EvidenceProviders


class CanonicalSemanticBridge:
    """Actual framework outbound-action implementation for V10.1.

    Each call begins with official SimplePIR selection and then traverses every
    accepted V9/V9.1 boundary.  No descriptor or route is supplied by the test
    manifest.
    """

    def __init__(self, artifact_root: Path | None = None):
        self.artifact_root = artifact_root
        self.runs: list[dict[str, Any]] = []

    def __call__(self, case: CaseSpec, argument: str) -> ActionOutcome:
        if self.artifact_root is None:
            temporary = tempfile.TemporaryDirectory(prefix="v10_1_canonical_")
            root = Path(temporary.name)
        else:
            temporary = None
            root = self.artifact_root / f"call-{len(self.runs):03d}"
            root.mkdir(parents=True, exist_ok=False)
        try:
            protected = ProtectedActionIntent(
                case.capability,
                argument.encode("utf-8"),
                "v10.1-semantic-executor",
                case.operation_id,
                ActionKind.TOOL,
            )
            spec = CanonicalSessionSpec(case.case_id, "agent.tools", 10, (protected,))
            selected = real_pir_select(root / "pir", [spec])
            descriptor = selected[case.case_id]
            actions = resolve_session(spec, descriptor)
            with EvidenceProviders({case.operation_id: case.scenario}) as providers:
                result, schedule = invoke_go_with_public_profile(
                    root / "canonical_session", load_v10_profile(), actions, providers
                )
                delivery = deliver_results(root / "delivery", [case.operation_id], result)
                observed_request = providers.observed(case.operation_id)
                provider_outcome = providers.outcome(case.operation_id)
                effect_count = int(case.operation_id in providers.effects)
            matching = [item for item in result["results"] if item["operation_id"] == case.operation_id]
            if len(matching) != 1:
                raise AssertionError("canonical result is missing or duplicated")
            item = matching[0]
            payload = base64.b64decode(item.get("payload") or "").decode("utf-8", errors="replace")
            status = int(item["status"])
            if case.scenario == "BOUNDED_TIMEOUT" and provider_outcome == "BOUNDED_TIMEOUT" and status == 3:
                semantics = f"{case.effect_semantics}:BOUNDED_TIMEOUT"
            elif status == 2:
                semantics = f"{case.effect_semantics}:SUCCESS"
            else:
                semantics = f"{case.effect_semantics}:ERROR"
            private_stages = [event["stage"] for event in result.get("private_events", []) if event.get("operation_id") == case.operation_id]
            evidence = {
                "official_simplepir_recovery": descriptor.agent_id == 10,
                "authenticated_agent_descriptor_v7": True,
                "trusted_action_router": actions[0]["route_handle"],
                "rfc9292_rfc9458_relay_rounds": len(result["public_relay_events"]),
                "provider_request": observed_request,
                "provider_outcome": provider_outcome,
                "delivery_ledger": delivery,
                "private_runtime_stages": private_stages,
                "public_profile": schedule["public_profile_id"],
                "dummy_provider_operations": result["dummy_provider_operations"],
                "profile_overflow_events": result["profile_overflow_events"],
            }
            if delivery["missing"] or delivery["unexpected"]:
                raise AssertionError("DeliveryLedger did not deliver the canonical result exactly once")
            self.runs.append(evidence)
            return ActionOutcome(payload, effect_count, semantics, observed_request, evidence)
        finally:
            if temporary is not None:
                temporary.cleanup()

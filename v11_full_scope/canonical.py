from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Protocol

from action_privacy_v8 import (
    ActionKind,
    AgentDescriptorV7,
    AgentDescriptorV7Codec,
    AgentServiceRouteDescriptor,
    DeliveryLedger,
    EffectSemantics,
    PlacementClass,
    PrivacyProfile,
    ProtectedActionIntent,
    TrustedActionRouter,
)
from action_privacy_v8.descriptor import AGENT_DESCRIPTOR_V7_BYTES
from canonical_v9.runner import (
    CanonicalSessionSpec,
    ROUTES,
    deliver_results,
    descriptor,
    real_pir_select,
    resolve_session,
)
from canonical_v9_1.projection import strict_size_projection, strict_structural_projection
from canonical_v9_1.runner import invoke_go_with_public_profile
from cryptographic_closure.pir_backend import PIRRequest, run_simplepir
from v10_holdout.harness import load_v10_profile

from .action_model import PrivateAgentServiceEnvelope, logical_request, protected_payload
from .models import (
    AgentServiceSubtype,
    CanonicalActionFamily,
    V11ActionCase,
    V11ActionOutcome,
)


ROOT = Path(__file__).resolve().parents[1]
V11_DESCRIPTOR_EPOCH = 20260829
STATUS_RESULT = 2


def _effect(value: str) -> EffectSemantics:
    return EffectSemantics(value)


def _canonical_ids(case: V11ActionCase) -> tuple[int, str, str, ActionKind]:
    if case.placement == "TRUSTED_MODULE_LOCAL":
        return 20, "agent.internal.20", "agent.internal.20", ActionKind.AGENT_SERVICE
    if case.agent_id == 21 and case.agent_capability == "agent.workflow.21":
        if case.action_family is CanonicalActionFamily.TOOL:
            capability = {
                "READ_ONLY": "tool.read",
                "IDEMPOTENT_EFFECT": "tool.idem",
                "NON_IDEMPOTENT_EFFECT": "tool.nonidem",
            }[case.effect_semantics]
            return 21, "agent.workflow.21", capability, ActionKind.TOOL
        if case.action_family is CanonicalActionFamily.EXTERNAL_HTTP:
            return 21, "agent.workflow.21", "external.local", ActionKind.EXTERNAL_HTTP
        if case.effect_semantics != "READ_ONLY":
            raise ValueError("development composite Agent-service route is READ_ONLY")
        return 21, "agent.workflow.21", "agent.workflow.21", ActionKind.AGENT_SERVICE
    selected = descriptor(case.agent_id)
    if case.agent_capability in selected.capability_ids:
        if case.action_family in {CanonicalActionFamily.TOOL, CanonicalActionFamily.EXTERNAL_HTTP}:
            route = ROUTES.get(case.capability)
            expected_kind = (
                ActionKind.TOOL
                if case.action_family is CanonicalActionFamily.TOOL
                else ActionKind.EXTERNAL_HTTP
            )
            if (
                route is not None
                and case.capability in selected.allowed_tool_capabilities
                and route.action_kind is expected_kind
                and route.effect_semantics.value == case.effect_semantics
            ):
                return case.agent_id, case.agent_capability, case.capability, expected_kind
        elif (
            selected.agent_service is not None
            and selected.agent_service.effect_semantics.value == case.effect_semantics
        ):
            return case.agent_id, case.agent_capability, case.agent_capability, ActionKind.AGENT_SERVICE
    if case.action_family is CanonicalActionFamily.TOOL:
        capability = {
            "READ_ONLY": "tool.read",
            "IDEMPOTENT_EFFECT": "tool.idem",
            "NON_IDEMPOTENT_EFFECT": "tool.nonidem",
        }[case.effect_semantics]
        return 10, "agent.tools", capability, ActionKind.TOOL
    if case.action_family is CanonicalActionFamily.EXTERNAL_HTTP:
        if case.effect_semantics != "READ_ONLY":
            raise ValueError("frozen EXTERNAL_HTTP route is READ_ONLY")
        return 10, "agent.tools", "external.local", ActionKind.EXTERNAL_HTTP
    agent_id = {
        "READ_ONLY": 11,
        "IDEMPOTENT_EFFECT": 12,
        "NON_IDEMPOTENT_EFFECT": 13,
    }[case.effect_semantics]
    return agent_id, f"agent.service.{agent_id}", f"agent.service.{agent_id}", ActionKind.AGENT_SERVICE


def _deterministic_result(request: dict[str, Any]) -> str:
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "V11_RESULT:" + hashlib.sha256(canonical.encode()).hexdigest()[:24]


@dataclass(frozen=True)
class ProviderObservation:
    operation_id: str
    route_handle: str
    logical_request: dict[str, Any]
    scenario: str


class V11EvidenceProviders:
    """Loopback provider set that decodes only the private V11 payload."""

    def __init__(
        self,
        cases: dict[str, V11ActionCase],
        private_evidence_path: Path | None = None,
    ):
        from canonical_v9.runner import Providers

        self._definitions = Providers.definitions
        self._cases = cases
        self.endpoints: dict[str, str] = {}
        self.observations: list[ProviderObservation] = []
        self.private_evidence: list[dict[str, Any]] = []
        self.private_evidence_path = private_evidence_path
        self.effects: set[str] = set()
        self._servers: list[ThreadingHTTPServer] = []
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()

    def __enter__(self) -> "V11EvidenceProviders":
        for route_handle, (_name, _minimum, _maximum, _effectful) in self._definitions.items():
            server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler(route_handle))
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
            thread.start()
            self._servers.append(server)
            self._threads.append(thread)
            self.endpoints[route_handle] = f"http://127.0.0.1:{server.server_port}/execute"
        return self

    def _handler(self, route_handle: str) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                started_ns = time.monotonic_ns()
                evidence: dict[str, Any] = {
                    "route_handle": route_handle,
                    "handler_start_monotonic_ns": started_ns,
                    "request_received": False,
                    "request_decoded_successfully": False,
                    "handler_logical_completion_monotonic_ns": 0,
                    "http_response_status_emitted": 0,
                    "encoded_response_bytes": 0,
                    "response_write_success": False,
                    "response_write_error_class": "",
                }
                length = int(self.headers.get("Content-Length", "0"))
                raw_request = self.rfile.read(length)
                evidence["request_received"] = True
                evidence["request_received_monotonic_ns"] = time.monotonic_ns()
                outer = json.loads(raw_request)
                operation_id = str(outer["operation_id"])
                evidence["operation_id"] = operation_id
                case = owner._cases[operation_id]
                payload = base64.b64decode(outer.get("payload", ""))
                if case.action_family is CanonicalActionFamily.AGENT_SERVICE:
                    envelope = PrivateAgentServiceEnvelope.decode(payload)
                    request = {
                        "operation_id": operation_id,
                        "action_family": "AGENT_SERVICE",
                        "agent_service_subtype": envelope.agent_service_subtype.value,
                        "arguments": envelope.arguments,
                    }
                else:
                    value = json.loads(payload)
                    request = {
                        "operation_id": operation_id,
                        "action_family": case.action_family.value,
                        "agent_service_subtype": None,
                        "arguments": value["arguments"],
                    }
                evidence["request_decoded_successfully"] = True
                evidence["request_decoded_monotonic_ns"] = time.monotonic_ns()
                with owner._lock:
                    owner.observations.append(
                        ProviderObservation(operation_id, route_handle, request, case.scenario)
                    )
                    if case.effect_semantics != "READ_ONLY" and case.scenario in {
                        "SUCCESS",
                        "BOUNDED_TIMEOUT",
                        "AMBIGUOUS_RESTART",
                    }:
                        owner.effects.add(operation_id)
                readiness_mode = case.continuation.get("provider_readiness_mode", "DEFAULT")
                readiness_delay = {
                    "DEFAULT": 0,
                    "EARLY_READY": 2,
                    "LATE_READY_WITHIN_BOUND": 30,
                }.get(readiness_mode)
                if readiness_delay is None:
                    evidence["handler_logical_completion_monotonic_ns"] = time.monotonic_ns()
                    evidence["http_response_status_emitted"] = 400
                    self.send_error(400)
                    evidence["response_write_success"] = True
                    evidence["handler_elapsed_ns"] = time.monotonic_ns() - started_ns
                    with owner._lock:
                        owner.private_evidence.append(evidence)
                    return
                if readiness_delay:
                    time.sleep(readiness_delay / 1000.0)
                if case.scenario in {"BOUNDED_TIMEOUT", "AMBIGUOUS_RESTART"}:
                    time.sleep(0.080)
                if case.scenario == "ERROR":
                    evidence["handler_logical_completion_monotonic_ns"] = time.monotonic_ns()
                    evidence["http_response_status_emitted"] = 503
                    self.send_error(503)
                    evidence["response_write_success"] = True
                    evidence["handler_elapsed_ns"] = time.monotonic_ns() - started_ns
                    with owner._lock:
                        owner.private_evidence.append(evidence)
                    return
                result = _deterministic_result(request).encode()
                encoded = json.dumps(
                    {"status": "OK", "payload": base64.b64encode(result).decode()}
                ).encode()
                evidence["handler_logical_completion_monotonic_ns"] = time.monotonic_ns()
                evidence["encoded_response_bytes"] = len(encoded)
                try:
                    self.send_response(200)
                    evidence["http_response_status_emitted"] = 200
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)
                    self.wfile.flush()
                    evidence["response_write_success"] = True
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as exc:
                    evidence["response_write_error_class"] = type(exc).__name__
                finally:
                    evidence["handler_elapsed_ns"] = time.monotonic_ns() - started_ns
                    with owner._lock:
                        owner.private_evidence.append(evidence)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        return Handler

    def __exit__(self, *_args: object) -> None:
        for server in self._servers:
            server.shutdown()
        for server in self._servers:
            server.server_close()
        for thread in self._threads:
            thread.join(timeout=2)
        if self.private_evidence_path is not None:
            self.private_evidence_path.write_text(
                json.dumps(self.private_evidence, indent=2) + "\n", encoding="utf-8"
            )

    def observed(self, operation_id: str) -> ProviderObservation:
        values = [value for value in self.observations if value.operation_id == operation_id]
        if len(values) != 1:
            raise AssertionError(f"expected one provider call for {operation_id}, got {len(values)}")
        return values[0]


def native_local_outcome(case: V11ActionCase) -> V11ActionOutcome:
    """Independent deterministic local action/Agent-service contract."""

    case.validate()
    request = logical_request(case)
    effect_count = int(
        case.effect_semantics != "READ_ONLY"
        and case.scenario in {"SUCCESS", "BOUNDED_TIMEOUT", "AMBIGUOUS_RESTART"}
    )
    if case.scenario == "SUCCESS":
        result = _deterministic_result(request)
        semantics = f"{case.effect_semantics}:SUCCESS"
    elif case.scenario == "ERROR":
        result = ""
        semantics = f"{case.effect_semantics}:ERROR"
    elif case.effect_semantics == "NON_IDEMPOTENT_EFFECT":
        result = ""
        semantics = "NON_IDEMPOTENT_EFFECT:EFFECT_OUTCOME_UNKNOWN"
    else:
        result = ""
        semantics = f"{case.effect_semantics}:BOUNDED_TIMEOUT"
    return V11ActionOutcome(
        result,
        effect_count,
        semantics,
        request,
        {"provider": "LOCAL_DETERMINISTIC_NATIVE_V11", "scenario": case.scenario},
    )


def canonical_external_outcome(
    case: V11ActionCase,
    output: Path,
    *,
    runner_binary: Path | None = None,
    plan_overrides: Mapping[str, object] | None = None,
) -> V11ActionOutcome:
    """Execute one external V11 action through the accepted canonical transport."""

    case.validate()
    if case.placement != "EXTERNAL":
        raise ValueError("external canonical bridge received an internal action")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite V11 artifacts: {output}")
    agent_id, agent_capability, capability, kind = _canonical_ids(case)
    protected = ProtectedActionIntent(
        capability,
        protected_payload(case),
        "v11-full-scope-development",
        case.operation_id,
        kind,
    )
    session = CanonicalSessionSpec(case.case_id, agent_capability, agent_id, (protected,))
    selected = real_pir_select(output / "pir", [session])
    resolved = resolve_session(session, selected[case.case_id])
    if resolved[0]["effect_semantics"] != case.effect_semantics:
        raise AssertionError("canonical route changed declared effect semantics")
    with V11EvidenceProviders({case.operation_id: case}) as providers:
        trace, schedule = invoke_go_with_public_profile(
            output / "canonical_session", load_v10_profile(), resolved, providers,
            runner_binary=runner_binary, plan_overrides=plan_overrides,
        )
        delivery = deliver_results(output / "delivery", [case.operation_id], trace)
        observation = providers.observed(case.operation_id)
        effect_count = int(case.operation_id in providers.effects)
    matching = [item for item in trace["results"] if item["operation_id"] == case.operation_id]
    if len(matching) != 1:
        raise AssertionError("canonical V11 result missing or duplicated")
    item = matching[0]
    status = int(item["status"])
    payload = base64.b64decode(item.get("payload") or "").decode("utf-8", errors="replace")
    if case.scenario == "SUCCESS" and status == STATUS_RESULT:
        semantics = f"{case.effect_semantics}:SUCCESS"
        result = payload
    elif case.scenario in {"BOUNDED_TIMEOUT", "AMBIGUOUS_RESTART"} and case.effect_semantics == "NON_IDEMPOTENT_EFFECT":
        semantics = "NON_IDEMPOTENT_EFFECT:EFFECT_OUTCOME_UNKNOWN"
        result = ""
    elif case.scenario == "BOUNDED_TIMEOUT":
        semantics = f"{case.effect_semantics}:BOUNDED_TIMEOUT"
        result = ""
    else:
        semantics = f"{case.effect_semantics}:ERROR"
        result = ""
    if delivery["missing"] or delivery["unexpected"]:
        raise AssertionError("canonical V11 DeliveryLedger mismatch")
    public_text = json.dumps(trace["public_relay_events"], sort_keys=True)
    for forbidden in (
        case.capability,
        case.operation_id,
        case.logical_action_name,
        case.agent_service_subtype.value if case.agent_service_subtype else "__none__",
    ):
        if forbidden != "__none__" and forbidden in public_text:
            raise AssertionError("Relay public evidence contains private V11 metadata")
    return V11ActionOutcome(
        result,
        effect_count,
        semantics,
        observation.logical_request,
        {
            "official_simplepir": True,
            "descriptor_authenticated": True,
            "trusted_route": resolved[0]["route_handle"],
            "private_subtype": case.agent_service_subtype.value if case.agent_service_subtype else None,
            "rfc9292_rfc9458": True,
            "public_profile": schedule["public_profile_id"],
            "relay_rounds": len(trace["public_relay_events"]),
            "dummy_provider_operations": trace["dummy_provider_operations"],
            "profile_overflow_events": trace["profile_overflow_events"],
            "delivery": delivery,
            "raw_trace": trace,
        },
    )


class TrustedExecutionBackend(Protocol):
    hardware_attested: bool

    def execute_internal(self, case: V11ActionCase) -> V11ActionOutcome: ...


class LocalTrustedBackendV11:
    """Software-only development backend; this is not a hardware TEE."""

    hardware_attested = False

    def execute_internal(self, case: V11ActionCase) -> V11ActionOutcome:
        if case.placement != "TRUSTED_MODULE_LOCAL":
            raise ValueError("local trusted backend received an external case")
        result = native_local_outcome(case)
        return V11ActionOutcome(
            result.result,
            result.effect_count,
            result.outcome_semantics,
            result.provider_visible_logical_request,
            {**result.evidence, "trusted_backend": "LOCAL_TRUSTED_BACKEND_V11", "hardware_tee": False},
        )


def internal_descriptor(agent_id: int = 20) -> AgentDescriptorV7:
    service = AgentServiceRouteDescriptor(
        "trusted-local-agent-20",
        EffectSemantics.READ_ONLY,
        "policy-trusted-local-agent-20",
        PlacementClass.TRUSTED_MODULE_LOCAL,
    )
    return AgentDescriptorV7(
        agent_id,
        ("agent.internal.20",),
        "publisher-local",
        1,
        PlacementClass.TRUSTED_MODULE_LOCAL,
        service,
        (),
        "LOCAL_TEST",
        V11_DESCRIPTOR_EPOCH,
    )


def real_pir_select_internal(output: Path, case_id: str, agent_id: int = 20) -> AgentDescriptorV7:
    output.mkdir(parents=True, exist_ok=False)
    key = os.urandom(32)
    codec = AgentDescriptorV7Codec(key, V11_DESCRIPTOR_EPOCH)
    registry = output / "encrypted_agent_descriptor_v7_rows.bin"
    with registry.open("xb") as handle:
        for row_id in range(1000):
            handle.write(codec.encode(internal_descriptor(row_id) if row_id == agent_id else descriptor(row_id)))
    if registry.stat().st_size != 1000 * AGENT_DESCRIPTOR_V7_BYTES:
        raise AssertionError("V11 internal registry size mismatch")
    artifacts = run_simplepir(
        ROOT,
        registry,
        1000,
        [PIRRequest(case_id, 0, agent_id, "PRIVATE_AGENT_SELECTION")],
        output / "simplepir",
    )
    recovered = codec.decode(artifacts.recovered[0], expected_agent_id=agent_id)
    if recovered != internal_descriptor(agent_id):
        raise AssertionError("internal Agent PIR recovery mismatch")
    return recovered


@dataclass(frozen=True)
class MultiplexedResult:
    operation_id: str
    source: str
    result: str
    outcome_semantics: str
    effect_count: int


class PrivateResultMultiplexer:
    def __init__(self, output: Path):
        self.output = output
        self._values: dict[str, MultiplexedResult] = {}

    def submit(self, operation_id: str, source: str, outcome: V11ActionOutcome) -> None:
        if source not in {"LOCAL_TRUSTED_RESULT", "OHTTP_GATEWAY_RESULT"}:
            raise ValueError("unknown private result source")
        if operation_id in self._values:
            raise ValueError("duplicate private result submission")
        self._values[operation_id] = MultiplexedResult(
            operation_id,
            source,
            outcome.result,
            outcome.outcome_semantics,
            outcome.effect_count,
        )

    def deliver(self, operation_id: str) -> dict[str, Any]:
        value = self._values[operation_id]
        ledger = DeliveryLedger(self.output / "trusted_delivery_ledger.json")
        sink: list[str] = []
        ledger.record_received(operation_id)
        ledger.mark_decapsulated(operation_id)
        ledger.deliver(operation_id, lambda: sink.append(value.result))
        decision = ledger.deliver(operation_id, lambda: sink.append("UNEXPECTED_DUPLICATE"))
        return {
            "source": value.source,
            "framework_sink": sink,
            "replay_suppressed": decision.value == "SUPPRESS_ALREADY_DELIVERED",
            "outcome_semantics": value.outcome_semantics,
            "effect_count": value.effect_count,
        }


def canonical_internal_outcome(
    case: V11ActionCase,
    output: Path,
    *,
    runner_binary: Path | None = None,
    plan_overrides: Mapping[str, object] | None = None,
) -> V11ActionOutcome:
    """Execute locally while sending a full fixed-profile NOOP/WAIT cover session."""

    case.validate()
    if case.placement != "TRUSTED_MODULE_LOCAL":
        raise ValueError("internal path requires TRUSTED_MODULE_LOCAL placement")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite V11 internal artifacts: {output}")
    output.mkdir(parents=True)
    recovered = real_pir_select_internal(output / "pir", case.case_id, case.agent_id)
    intent = ProtectedActionIntent(
        case.capability,
        protected_payload(case),
        "v11-internal-development",
        case.operation_id,
        ActionKind.AGENT_SERVICE,
    )
    router = TrustedActionRouter({})
    resolved = router.resolve(intent, recovered, PrivacyProfile.STRICT)
    if resolved.placement is not PlacementClass.TRUSTED_MODULE_LOCAL:
        raise AssertionError("internal Agent did not resolve to trusted-module-local")
    outcome = LocalTrustedBackendV11().execute_internal(case)
    # The public transport receives no real action.  Every one of the 111
    # profile rounds is still emitted as encrypted NOOP/WAIT cover.
    with V11EvidenceProviders({}) as providers:
        cover_trace, schedule = invoke_go_with_public_profile(
            output / "cover_session", load_v10_profile(), [], providers,
            runner_binary=runner_binary, plan_overrides=plan_overrides,
        )
    if cover_trace["provider_invocations"] != 0 or cover_trace["dummy_provider_operations"] != 0:
        raise AssertionError("internal cover traffic caused provider work")
    mux = PrivateResultMultiplexer(output / "delivery")
    mux.submit(case.operation_id, "LOCAL_TRUSTED_RESULT", outcome)
    delivered = mux.deliver(case.operation_id)
    return V11ActionOutcome(
        outcome.result,
        outcome.effect_count,
        outcome.outcome_semantics,
        outcome.provider_visible_logical_request,
        {
            **outcome.evidence,
            "official_simplepir": True,
            "descriptor_authenticated": True,
            "placement": resolved.placement.value,
            "public_profile": schedule["public_profile_id"],
            "cover_trace": cover_trace,
            "result_multiplexer": delivered,
            "dummy_provider_operations": 0,
        },
    )


def public_projections(outcome: V11ActionOutcome) -> tuple[dict[str, Any], dict[str, Any]]:
    trace = outcome.evidence.get("raw_trace") or outcome.evidence.get("cover_trace")
    if not isinstance(trace, dict):
        raise ValueError("outcome has no public Relay trace")
    profile = load_v10_profile()
    return strict_structural_projection(trace, profile), strict_size_projection(trace, profile)


def canonical_multi_action(
    cases: list[V11ActionCase],
    output: Path,
    *,
    runner_binary: Path | None = None,
    plan_overrides: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Execute one development session containing multiple same-Agent actions."""

    if not cases or len(cases) > load_v10_profile().maximum_real_operations:
        raise ValueError("multi-action workload is outside the public capacity")
    if output.exists():
        raise FileExistsError("refusing to overwrite V11 multi-action evidence")
    for case in cases:
        case.validate()
        if case.placement != "EXTERNAL":
            raise ValueError("multi-action development helper currently accepts external cases")
    identities = [_canonical_ids(case) for case in cases]
    if len({(value[0], value[1]) for value in identities}) != 1:
        raise ValueError("one canonical session must use one privately selected Agent")
    agent_id, agent_capability = identities[0][:2]
    intents = tuple(
        ProtectedActionIntent(
            capability,
            protected_payload(case),
            "v11-multi-action-development",
            case.operation_id,
            kind,
        )
        for case, (_agent_id, _agent_capability, capability, kind) in zip(cases, identities, strict=True)
    )
    session = CanonicalSessionSpec("v11-multi-action", agent_capability, agent_id, intents)
    selected = real_pir_select(output / "pir", [session])
    resolved = resolve_session(session, selected[session.case_id])
    with V11EvidenceProviders({case.operation_id: case for case in cases}) as providers:
        trace, schedule = invoke_go_with_public_profile(
            output / "canonical_session", load_v10_profile(), resolved, providers,
            runner_binary=runner_binary, plan_overrides=plan_overrides,
        )
        delivery = deliver_results(output / "delivery", [case.operation_id for case in cases], trace)
        observations = [asdict(providers.observed(case.operation_id)) for case in cases]
    functional = (
        not delivery["missing"]
        and not delivery["unexpected"]
        and int(trace["provider_invocations"]) == len(cases)
        and int(trace["dummy_provider_operations"]) == 0
        and int(trace["profile_overflow_events"]) == 0
    )
    return {
        "functional": functional,
        "admitted": len(cases),
        "provider_invocations": trace["provider_invocations"],
        "delivered": len(delivery["framework_sink"]),
        "dummy_provider_operations": trace["dummy_provider_operations"],
        "profile_overflow_events": trace["profile_overflow_events"],
        "official_simplepir": True,
        "descriptor_authenticated": True,
        "public_profile": schedule["public_profile_id"],
        "provider_observations": observations,
        "strict_structural_projection": strict_structural_projection(trace, load_v10_profile()),
        "strict_size_projection": strict_size_projection(trace, load_v10_profile()),
        "raw_trace": trace,
    }


def canonical_mixed_workflow(
    cases: list[V11ActionCase],
    output: Path,
    *,
    runner_binary: Path | None = None,
    plan_overrides: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Run a true mixed Tool/Agent-service development workflow in one session.

    Agent 21 is a development-only composite descriptor whose authenticated
    capsule authorizes the existing Tool routes and one existing-style Agent
    service route.  Every step still traverses one PIR-selected descriptor,
    TrustedActionRouter, OHTTP transport, Gateway, and DeliveryLedger.
    """

    if not cases or len(cases) > load_v10_profile().maximum_real_operations:
        raise ValueError("mixed workflow is outside the public capacity")
    if output.exists():
        raise FileExistsError("refusing to overwrite V11.1 mixed-workflow evidence")
    for case in cases:
        case.validate()
        if case.placement != "EXTERNAL":
            raise ValueError("mixed workflow accepts external actions only")

    intents: list[ProtectedActionIntent] = []
    for case in cases:
        if case.action_family is CanonicalActionFamily.TOOL:
            capability = {
                "READ_ONLY": "tool.read",
                "IDEMPOTENT_EFFECT": "tool.idem",
                "NON_IDEMPOTENT_EFFECT": "tool.nonidem",
            }[case.effect_semantics]
            kind = ActionKind.TOOL
        elif case.action_family is CanonicalActionFamily.EXTERNAL_HTTP:
            capability = "external.local"
            kind = ActionKind.EXTERNAL_HTTP
        else:
            if case.effect_semantics != "READ_ONLY":
                raise ValueError("development composite Agent-service route is READ_ONLY")
            capability = "agent.workflow.21"
            kind = ActionKind.AGENT_SERVICE
        intents.append(
            ProtectedActionIntent(
                capability,
                protected_payload(case),
                "v11-1-mixed-workflow-development",
                case.operation_id,
                kind,
            )
        )

    session = CanonicalSessionSpec(
        "v11-1-mixed-workflow",
        "agent.workflow.21",
        21,
        tuple(intents),
    )
    selected = real_pir_select(output / "pir", [session])
    resolved = resolve_session(session, selected[session.case_id])
    with V11EvidenceProviders({case.operation_id: case for case in cases}) as providers:
        trace, schedule = invoke_go_with_public_profile(
            output / "canonical_session",
            load_v10_profile(),
            resolved,
            providers,
            runner_binary=runner_binary,
            plan_overrides=plan_overrides,
        )
        delivery = deliver_results(output / "delivery", [case.operation_id for case in cases], trace)
        observations = [asdict(providers.observed(case.operation_id)) for case in cases]
        effect_count = len(providers.effects)

    delivered_ids = [str(item["operation_id"]) for item in trace["results"]]
    expected_ids = [case.operation_id for case in cases]
    functional = (
        not delivery["missing"]
        and not delivery["unexpected"]
        and sorted(delivered_ids) == sorted(expected_ids)
        and int(trace["provider_invocations"]) == len(cases)
        and int(trace["dummy_provider_operations"]) == 0
        and int(trace["profile_overflow_events"]) == 0
        and trace.get("session_status") == "COMPLETE"
    )
    return {
        "functional": functional,
        "workflow": [
            case.agent_service_subtype.value
            if case.agent_service_subtype is not None
            else case.action_family.value
            for case in cases
        ],
        "admitted": len(cases),
        "provider_invocations": trace["provider_invocations"],
        "delivered": len(delivery["framework_sink"]),
        "delivered_operation_ids": delivered_ids,
        "expected_operation_ids": expected_ids,
        "operation_id_association": sorted(delivered_ids) == sorted(expected_ids),
        "provider_observations": observations,
        "effect_count": effect_count,
        "dummy_provider_operations": trace["dummy_provider_operations"],
        "profile_overflow_events": trace["profile_overflow_events"],
        "official_simplepir": True,
        "descriptor_authenticated": True,
        "public_profile": schedule["public_profile_id"],
        "session_status": trace.get("session_status"),
        "strict_structural_projection": strict_structural_projection(trace, load_v10_profile()),
        "strict_size_projection": strict_size_projection(trace, load_v10_profile()),
        "raw_trace": trace,
    }


def outcome_json(outcome: V11ActionOutcome) -> dict[str, Any]:
    return asdict(outcome)

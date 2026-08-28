from __future__ import annotations

import hashlib
import json
import math
import random
import time
from dataclasses import asdict, dataclass, replace
from typing import Mapping

from src.path_oram import PathORAM

from .ir import IROperation, MediationProgram, Transition, Visibility, build_program


VARIANTS = ("B0-NATURAL", "B1-PER-ACTION-OBLIVIOUS", "B2-ADAPTIVE-OBLIVIOUS")
TASKS = ("SEND_MESSAGE", "SHARE_DOCUMENT")
SCENARIOS = ("AUTHORIZATION", "PROVENANCE", "EXTRA_VERIFICATION")
FORBIDDEN_TRACE_FIELDS = {
    "permission_exists",
    "provenance_exists",
    "requires_extra_verification",
    "private_branch",
    "private_label",
    "is_dummy",
    "logical_id",
    "record_key",
    "consent_required",
}


@dataclass(frozen=True)
class PublicTask:
    action_type: str
    recipient_handle: str
    document_handle: str

    def __post_init__(self) -> None:
        if self.action_type not in TASKS:
            raise ValueError(self.action_type)


@dataclass(frozen=True)
class PrivateMediationState:
    entity: int
    policy_profile: int
    permission_exists: bool = True
    provenance_exists: bool = True
    requires_extra_verification: bool = False
    local_consent_grants: bool = True

    def evaluation_state(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Episode:
    episode_id: int
    scenario: str
    task: PublicTask
    private_state: PrivateMediationState
    generation_order: tuple[str, ...] = ("private_state", "public_task", "execute", "derive_label")


@dataclass(frozen=True)
class NormalizedPlan:
    horizon: int
    required_horizon: int
    overflow: bool
    public_round_slots: tuple[int, ...]
    public_commit_round: int | None


class AdaptiveNormalizer:
    """Shared, task-agnostic bounded adaptive normalizer.

    The compiler reads only graph structure, annotations, and H. It never reads
    task names or private guard values.  The external effect endpoint remains a
    public task-schema parameter used only by the executor at the fixed commit.
    """

    def compile(self, program: MediationProgram, horizon: int) -> NormalizedPlan:
        if horizon <= 0:
            raise ValueError("horizon must be positive")
        required = program.required_horizon
        overflow = required > horizon
        return NormalizedPlan(
            horizon=horizon,
            required_horizon=required,
            overflow=overflow,
            public_round_slots=tuple(range(1, horizon + 1)),
            public_commit_round=None if overflow else horizon,
        )


class _PrivateStorage:
    """One existing Path-ORAM instance used as a Stage-9 building block."""

    def __init__(self, seed: int):
        self.oram = PathORAM(128, seed, 4, math.ceil(math.log2(128)))

    def access(self, key: str, operation: str) -> dict[str, object]:
        block_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") % 128
        _, physical = self.oram.access(block_id, operation, f"synthetic:{key}" if operation == "write" else None)
        return physical


class MediationExecutor:
    """Execute natural, per-action, or bounded adaptive mediation locally."""

    STATE_SERVICE = "PRIVATE_STATE_ORAM"
    COORDINATOR = "MEDIATION_COORDINATOR"

    def __init__(self, variant: str, horizon: int = 5, seed: int = 0):
        if variant not in VARIANTS:
            raise ValueError(variant)
        self.variant = variant
        self.horizon = horizon
        self.storage = _PrivateStorage(seed)
        self.normalizer = AdaptiveNormalizer()
        self.host_trace: list[dict[str, object]] = []
        self.private_trace: list[dict[str, object]] = []
        self.effects: list[dict[str, str]] = []
        self.real_private_ops = 0
        self.dummy_private_ops = 0
        self.oram_accesses = 0
        self.started_ns = 0
        self.effect_ns: int | None = None

    @staticmethod
    def _effect_service(task: PublicTask) -> str:
        # Task schema supplies a public endpoint. The compiler does not branch on it.
        return {"SEND_MESSAGE": "MESSAGE_TOOL", "SHARE_DOCUMENT": "DOCUMENT_TOOL"}[task.action_type]

    @staticmethod
    def _serialized_bytes(payload: Mapping[str, object]) -> int:
        return len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()) + 4

    def _append_host(self, round_index: int, service: str, operation: str, *, physical: Mapping[str, object] | None = None) -> None:
        request = {"operation": operation, "protected": "Q" * 192}
        response = {"ok": True, "protected": "R" * 192}
        event: dict[str, object] = {
            "round": round_index,
            "destination_service": service,
            "operation_class": operation,
            "request_bytes": self._serialized_bytes(request),
            "response_bytes": self._serialized_bytes(response),
            "public_round_boundary": True,
        }
        if physical is not None:
            event["physical_path"] = int(physical["leaf"])
        self.host_trace.append(event)

    def _private_access(self, round_index: int, operation: str, semantic_key: str, *, dummy: bool) -> None:
        physical = self.storage.access(semantic_key, operation)
        self._append_host(round_index, self.STATE_SERVICE, "ORAM_ACCESS", physical=physical)
        self.private_trace.append({
            "round": round_index,
            "operation": operation,
            "semantic_key": semantic_key,
            "is_dummy": dummy,
        })
        self.oram_accesses += 1
        if dummy:
            self.dummy_private_ops += 1
        else:
            self.real_private_ops += 1

    def _natural_event(self, round_index: int, operation: IROperation) -> None:
        if operation.visibility == Visibility.PRIVATE:
            self.real_private_ops += 1
        service = {
            "RESOLVE": "PRIVATE_DATA_DB",
            "AUTHORIZE": "PERMISSION_DB",
            "CHECK_PROVENANCE": "DISCLOSURE_LOG",
            "REQUEST_LOCAL_CONSENT": "LOCAL_CONSENT",
            "PERSIST_AUTHORIZATION": "PERMISSION_DB",
            "REBUILD_PROVENANCE": "PROVENANCE_ENGINE",
            "PERSIST_PROVENANCE": "DISCLOSURE_LOG",
            "VERIFY_AUTHORIZATION": "PERMISSION_DB",
            "PREPARE_EFFECT": self.COORDINATOR,
            "RETURN_SANITIZED": self.COORDINATOR,
        }.get(operation.kind)
        if service is not None:
            self._append_host(round_index, service, operation.kind)

    def _apply(self, operation: IROperation, state: dict[str, object], task: PublicTask, round_index: int) -> None:
        if operation.kind == "REQUEST_LOCAL_CONSENT":
            # A real trusted interaction, never a dummy prompt. Timing is not shaped.
            time.sleep(0.00025)
            if not bool(state["local_consent_grants"]):
                state["authorization_denied"] = True
        elif operation.kind == "PERSIST_AUTHORIZATION" and not state.get("authorization_denied"):
            state["permission_exists"] = True
        elif operation.kind in {"REBUILD_PROVENANCE", "PERSIST_PROVENANCE"}:
            state["provenance_exists"] = True
        elif operation.kind == "VERIFY_AUTHORIZATION":
            state["requires_extra_verification"] = False
        elif operation.kind == "COMMIT_EFFECT":
            if state.get("authorization_denied"):
                return
            self.effects.append({
                "action_type": task.action_type,
                "recipient": f"synthetic_{task.recipient_handle.lower()}@example.invalid",
                "document": f"synthetic_{task.document_handle.lower()}",
            })
            self.effect_ns = time.perf_counter_ns()

    def _select_path(self, program: MediationProgram, state: dict[str, object]) -> tuple[Transition, ...]:
        current = program.initial_state
        path: list[Transition] = []
        while current != program.terminal_state:
            eligible = [transition for transition in program.outgoing(current) if transition.guard.evaluate(state)]
            if len(eligible) != 1:
                raise RuntimeError(f"expected one eligible transition from {current}, got {len(eligible)}")
            transition = eligible[0]
            path.append(transition)
            current = transition.target
        return tuple(path)

    @staticmethod
    def _fresh_state(private_state: PrivateMediationState) -> dict[str, object]:
        state = private_state.evaluation_state()
        state["authorization_denied"] = False
        return state

    def execute(self, episode: Episode) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
        self.started_ns = time.perf_counter_ns()
        program = build_program(episode.scenario)
        state = self._fresh_state(episode.private_state)

        # Path selection runs on a disposable copy so it cannot double-apply
        # mutations when the selected semantic operations are executed below.
        selection_state = dict(state)
        path = self._select_path(program, selection_state)
        natural_rounds = len(path)
        overflow = False

        if self.variant == "B2-ADAPTIVE-OBLIVIOUS":
            plan = self.normalizer.compile(program, self.horizon)
            overflow = plan.overflow
            if overflow:
                for round_index in plan.public_round_slots:
                    for slot in range(3):
                        self._private_access(round_index, "read", f"overflow:{round_index}:{slot}", dummy=True)
                authorized = False
                final_outcome = "HORIZON_EXCEEDED"
            else:
                precommit = [transition for transition in path if not any(op.external_effect for op in transition.operations)]
                commit = next(transition for transition in path if any(op.external_effect for op in transition.operations))
                for round_index in range(1, self.horizon):
                    real_transition = precommit[round_index - 1] if round_index <= len(precommit) else None
                    operations = real_transition.operations if real_transition is not None else ()
                    for operation in operations:
                        self._apply(operation, state, episode.task, round_index)
                    real_slots = min(3, max(1, len([op for op in operations if not op.external_effect]))) if real_transition else 0
                    for slot in range(3):
                        key = f"real:{episode.private_state.entity}:{round_index}:{slot}" if slot < real_slots else f"pad:{round_index}:{slot}"
                        self._private_access(round_index, "read", key, dummy=slot >= real_slots)
                for operation in commit.operations:
                    self._apply(operation, state, episode.task, self.horizon)
                for slot in range(3):
                    self._private_access(self.horizon, "read", f"commit-pad:{self.horizon}:{slot}", dummy=True)
                if self.effects:
                    self._append_host(self.horizon, self._effect_service(episode.task), "PUBLIC_EFFECT")
                authorized = bool(self.effects)
                final_outcome = "SUCCESS" if authorized else "DENY"
        else:
            for round_index, transition in enumerate(path, 1):
                if self.variant == "B1-PER-ACTION-OBLIVIOUS":
                    for operation in transition.operations:
                        self._apply(operation, state, episode.task, round_index)
                    private_count = len([operation for operation in transition.operations if operation.visibility == Visibility.PRIVATE])
                    real_slots = min(3, private_count)
                    for slot in range(3):
                        key = f"real:{episode.private_state.entity}:{round_index}:{slot}" if slot < real_slots else f"pad:{round_index}:{slot}"
                        self._private_access(round_index, "read", key, dummy=slot >= real_slots)
                    if any(op.external_effect for op in transition.operations) and self.effects:
                        self._append_host(round_index, self._effect_service(episode.task), "PUBLIC_EFFECT")
                else:
                    for operation in transition.operations:
                        self._apply(operation, state, episode.task, round_index)
                        if operation.external_effect:
                            if self.effects:
                                self._append_host(round_index, self._effect_service(episode.task), "PUBLIC_EFFECT")
                        else:
                            self._natural_event(round_index, operation)
            authorized = bool(self.effects)
            final_outcome = "SUCCESS" if authorized else "DENY"

        elapsed_us = (time.perf_counter_ns() - self.started_ns) / 1000
        effect_latency_us = ((self.effect_ns - self.started_ns) / 1000) if self.effect_ns is not None else 0.0
        result: dict[str, object] = {
            "authorized": authorized,
            "effect_count": len(self.effects),
            "effect": self.effects[0] if self.effects else None,
            "permission_exists": bool(state["permission_exists"]),
            "provenance_exists": bool(state["provenance_exists"]),
            "requires_extra_verification": bool(state["requires_extra_verification"]),
            "sanitized_response": "completed" if authorized else final_outcome.lower(),
            "final_outcome": final_outcome,
            "natural_rounds": natural_rounds,
            "visible_rounds": max((int(event["round"]) for event in self.host_trace), default=self.horizon if overflow else 0),
            "real_private_ops": self.real_private_ops,
            "dummy_private_ops": self.dummy_private_ops,
            "oram_accesses": self.oram_accesses,
            "wire_bytes": sum(int(event["request_bytes"]) + int(event["response_bytes"]) for event in self.host_trace),
            "latency_us": elapsed_us,
            "effect_latency_us": effect_latency_us,
            "trusted_state_bytes": 32 + len(self.storage.oram.position) * 4 + len(self.storage.oram.stash) * 64,
            "overflow": overflow,
        }
        assert_public_trace(self.host_trace)
        return result, list(self.host_trace), list(self.private_trace)


def assert_public_trace(trace: list[dict[str, object]]) -> None:
    encoded = json.dumps(trace, sort_keys=True)
    for field in FORBIDDEN_TRACE_FIELDS:
        if field in encoded:
            raise AssertionError(f"private field leaked to host trace: {field}")


def make_paired_episode(episode_id: int, scenario: str, task_type: str, branch: int, entity: int, policy_profile: int) -> Episode:
    base = PrivateMediationState(entity=entity, policy_profile=policy_profile)
    if scenario == "AUTHORIZATION":
        state = replace(base, permission_exists=not bool(branch))
    elif scenario == "PROVENANCE":
        state = replace(base, provenance_exists=not bool(branch))
    elif scenario == "EXTRA_VERIFICATION":
        state = replace(base, requires_extra_verification=bool(branch))
    else:
        raise ValueError(scenario)
    return Episode(
        episode_id,
        scenario,
        # Paired branches receive consecutive episode IDs but exactly the same
        # public task and final effect arguments.
        PublicTask(task_type, f"CONTACT_{entity % 32}", f"DOCUMENT_{(episode_id // 2) % 48}"),
        state,
    )


def derive_private_label(episode: Episode) -> int:
    """Called by the harness only after trace capture."""

    state = episode.private_state
    if episode.scenario == "AUTHORIZATION":
        return int(not state.permission_exists)
    if episode.scenario == "PROVENANCE":
        return int(not state.provenance_exists)
    return int(state.requires_extra_verification)


def run_dynamic_planning_example() -> dict[str, object]:
    """Deterministic planner/mediator follow-up example with no LLM claim."""

    task = PublicTask("SEND_MESSAGE", "CONTACT_17", "DOCUMENT_8")
    private_state = PrivateMediationState(entity=17, policy_profile=2, permission_exists=False)
    transcript: list[dict[str, object]] = [{"actor": "planner", "event": "PROPOSE_ACTION", "task": task.action_type}]
    if not private_state.permission_exists:
        # The reason stays trusted; the planner sees only a sanitized continuation.
        transcript.append({"actor": "mediator", "event": "SANITIZED_RESULT", "result": "CONTINUE"})
        private_state = replace(private_state, permission_exists=private_state.local_consent_grants)
        transcript.append({"actor": "planner", "event": "SUBMIT_FOLLOW_UP", "task": task.action_type})
    episode = Episode(808, "AUTHORIZATION", task, private_state)
    result, host_trace, _ = MediationExecutor("B0-NATURAL", 5, 808).execute(episode)
    transcript.append({"actor": "mediator", "event": "SANITIZED_RESULT", "result": result["sanitized_response"]})
    return {"transcript": transcript, "result": result, "host_trace": host_trace}

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping


class Visibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


IR_KINDS = (
    "RESOLVE",
    "AUTHORIZE",
    "CHECK_PROVENANCE",
    "REQUEST_LOCAL_CONSENT",
    "PERSIST_AUTHORIZATION",
    "REBUILD_PROVENANCE",
    "PERSIST_PROVENANCE",
    "VERIFY_AUTHORIZATION",
    "PREPARE_EFFECT",
    "COMMIT_EFFECT",
    "RETURN_SANITIZED",
)


@dataclass(frozen=True)
class Guard:
    """A control-flow guard with an explicit leakage annotation."""

    name: str
    visibility: Visibility
    predicate: Callable[[Mapping[str, object]], bool]

    def evaluate(self, state: Mapping[str, object]) -> bool:
        return bool(self.predicate(state))


@dataclass(frozen=True)
class IROperation:
    """One security-relevant operation in the deliberately small IR."""

    kind: str
    visibility: Visibility = Visibility.PRIVATE
    external_effect: bool = False

    def __post_init__(self) -> None:
        if self.kind not in IR_KINDS:
            raise ValueError(f"unknown mediation IR operation: {self.kind}")
        if self.external_effect != (self.kind == "COMMIT_EFFECT"):
            raise ValueError("COMMIT_EFFECT is the only external-effect operation")


@dataclass(frozen=True)
class Transition:
    source: str
    target: str
    guard: Guard
    operations: tuple[IROperation, ...]


@dataclass(frozen=True)
class MediationProgram:
    """A finite acyclic state machine for one mediation scenario."""

    name: str
    initial_state: str
    terminal_state: str
    transitions: tuple[Transition, ...]

    def outgoing(self, state: str) -> tuple[Transition, ...]:
        return tuple(t for t in self.transitions if t.source == state)

    def all_paths(self) -> tuple[tuple[Transition, ...], ...]:
        paths: list[tuple[Transition, ...]] = []

        def visit(state: str, path: tuple[Transition, ...], seen: frozenset[str]) -> None:
            if state == self.terminal_state:
                paths.append(path)
                return
            if state in seen:
                raise ValueError(f"cyclic mediation IR is outside Stage-9 scope: {state}")
            options = self.outgoing(state)
            if not options:
                raise ValueError(f"non-terminal IR state has no transition: {state}")
            for transition in options:
                visit(transition.target, path + (transition,), seen | {state})

        visit(self.initial_state, (), frozenset())
        return tuple(paths)

    @property
    def required_horizon(self) -> int:
        return max(len(path) for path in self.all_paths())


ALWAYS = Guard("always", Visibility.PUBLIC, lambda _state: True)


def op(kind: str) -> IROperation:
    return IROperation(kind, Visibility.PUBLIC if kind in {"COMMIT_EFFECT", "RETURN_SANITIZED"} else Visibility.PRIVATE, kind == "COMMIT_EFFECT")


def _program_authorization() -> MediationProgram:
    exists = Guard("permission_exists", Visibility.PRIVATE, lambda s: bool(s["permission_exists"]))
    missing = Guard("permission_missing", Visibility.PRIVATE, lambda s: not bool(s["permission_exists"]))
    return MediationProgram(
        "existing_vs_missing_authorization",
        "START",
        "DONE",
        (
            Transition("START", "CHECKED", ALWAYS, (op("RESOLVE"), op("AUTHORIZE"))),
            Transition("CHECKED", "READY", exists, (op("PREPARE_EFFECT"),)),
            Transition("CHECKED", "CONSENTED", missing, (op("REQUEST_LOCAL_CONSENT"), op("PERSIST_AUTHORIZATION"))),
            Transition("CONSENTED", "VERIFIED", ALWAYS, (op("VERIFY_AUTHORIZATION"),)),
            Transition("VERIFIED", "READY", ALWAYS, (op("PREPARE_EFFECT"),)),
            Transition("READY", "DONE", ALWAYS, (op("COMMIT_EFFECT"), op("RETURN_SANITIZED"))),
        ),
    )


def _program_provenance() -> MediationProgram:
    exists = Guard("provenance_exists", Visibility.PRIVATE, lambda s: bool(s["provenance_exists"]))
    missing = Guard("provenance_missing", Visibility.PRIVATE, lambda s: not bool(s["provenance_exists"]))
    return MediationProgram(
        "existing_vs_missing_provenance",
        "START",
        "DONE",
        (
            Transition("START", "CHECKED", ALWAYS, (op("RESOLVE"), op("CHECK_PROVENANCE"))),
            Transition("CHECKED", "READY", exists, (op("PREPARE_EFFECT"),)),
            Transition("CHECKED", "REBUILT", missing, (op("REBUILD_PROVENANCE"), op("PERSIST_PROVENANCE"))),
            Transition("REBUILT", "READY", ALWAYS, (op("PREPARE_EFFECT"),)),
            Transition("READY", "DONE", ALWAYS, (op("COMMIT_EFFECT"), op("RETURN_SANITIZED"))),
        ),
    )


def _program_extra_verification() -> MediationProgram:
    cached = Guard("verification_cached", Visibility.PRIVATE, lambda s: not bool(s["requires_extra_verification"]))
    required = Guard("extra_verification_required", Visibility.PRIVATE, lambda s: bool(s["requires_extra_verification"]))
    return MediationProgram(
        "policy_extra_verification",
        "START",
        "DONE",
        (
            Transition("START", "CHECKED", ALWAYS, (op("RESOLVE"), op("AUTHORIZE"))),
            Transition("CHECKED", "READY", cached, (op("PREPARE_EFFECT"),)),
            Transition("CHECKED", "VERIFIED", required, (op("VERIFY_AUTHORIZATION"),)),
            Transition("VERIFIED", "READY", ALWAYS, (op("PREPARE_EFFECT"),)),
            Transition("READY", "DONE", ALWAYS, (op("COMMIT_EFFECT"), op("RETURN_SANITIZED"))),
        ),
    )


PROGRAM_BUILDERS = {
    "AUTHORIZATION": _program_authorization,
    "PROVENANCE": _program_provenance,
    "EXTRA_VERIFICATION": _program_extra_verification,
}


def build_program(scenario: str) -> MediationProgram:
    """Build scenario IR without consulting the public task/effect name."""

    try:
        return PROGRAM_BUILDERS[scenario]()
    except KeyError as exc:
        raise ValueError(f"unknown Stage-9 scenario: {scenario}") from exc

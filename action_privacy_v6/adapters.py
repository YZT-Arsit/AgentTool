from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import ActionKind, ProtectedActionIntent


@dataclass(frozen=True)
class NativeAction:
    framework: str
    source_path: str
    action_name: str
    action_kind: ActionKind
    arguments: bytes
    operation_id: str


@dataclass(frozen=True)
class ActionProjection:
    selected_action: str
    arguments: str
    result: str
    effect_count: int
    operation_id: str
    outcome: str


class FrameworkActionAdapter:
    """Narrow outbound-action seam; native reasoning remains untouched."""

    def __init__(self, framework: str):
        self.framework = framework

    def intercept(self, action: NativeAction, *, session_id: str) -> ProtectedActionIntent:
        if action.framework != self.framework:
            raise ValueError("framework adapter mismatch")
        return ProtectedActionIntent(action.action_name, action.arguments, session_id,
                                     action.operation_id, action.action_kind)


class DeterministicLocalProvider:
    def __init__(self):
        self.effects: set[str] = set()

    def invoke(self, action_name: str, arguments: bytes, operation_id: str, *, effectful: bool) -> ActionProjection:
        if effectful:
            self.effects.add(operation_id)
        result = f"local:{action_name}:{arguments.decode('utf-8')}"
        return ActionProjection(action_name, arguments.decode("utf-8"), result,
                                int(effectful and operation_id in self.effects), operation_id, "SUCCESS")


def execute_native(action: NativeAction, provider: DeterministicLocalProvider, *, effectful: bool) -> ActionProjection:
    return provider.invoke(action.action_name, action.arguments, action.operation_id, effectful=effectful)


def execute_mediated(action: NativeAction, adapter: FrameworkActionAdapter,
                     trusted_dispatch: Callable[[ProtectedActionIntent], ActionProjection], *, session_id: str) -> ActionProjection:
    return trusted_dispatch(adapter.intercept(action, session_id=session_id))

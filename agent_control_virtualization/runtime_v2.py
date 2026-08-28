from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Callable, Protocol, Sequence

from .ir_v2 import (AgentProgramV2, ContextItem, DecisionKind, ModelDecision,
                    ProgramBundleV2, RuntimeState, StateScope, ToolCall,
                    private_handle)


class PrivateStateStore:
    """Bounded scoped state used only inside the trusted interpreter.

    This implements the restricted GET/SET/EXISTS subset. It does not claim
    automatic lowering of arbitrary framework session or persistence objects.
    """

    def __init__(self, *, max_entries_per_namespace: int = 64):
        if max_entries_per_namespace < 1:
            raise ValueError("state namespace bound must be positive")
        self.max_entries_per_namespace = max_entries_per_namespace
        self._namespaces: dict[tuple[StateScope, str], dict[str, object]] = {}

    def _namespace(self, scope: StateScope, owner: str) -> dict[str, object]:
        if not owner:
            raise ValueError("state owner must be explicit")
        return self._namespaces.setdefault((scope, owner), {})

    def exists(self, scope: StateScope, owner: str, key: str) -> bool:
        return key in self._namespace(scope, owner)

    def get(self, scope: StateScope, owner: str, key: str) -> object:
        return self._namespace(scope, owner)[key]

    def set(self, scope: StateScope, owner: str, key: str, value: object) -> None:
        namespace = self._namespace(scope, owner)
        if key not in namespace and len(namespace) >= self.max_entries_per_namespace:
            raise OverflowError("private state namespace bound exceeded")
        namespace[key] = value

    def snapshot(self, scope: StateScope, owner: str) -> dict[str, object]:
        return dict(self._namespace(scope, owner))


class ModelAdapter(Protocol):
    def __call__(self, agent: AgentProgramV2, context: tuple[ContextItem, ...]) -> ModelDecision: ...


class ToolAdapter(Protocol):
    def __call__(self, arguments: dict[str, object]) -> object: ...


@dataclass(frozen=True)
class ToolBinding:
    name: str
    invoke: ToolAdapter
    effectful: bool = False


@dataclass(frozen=True)
class PrivateStep:
    ordinal: int
    logical_agent_id: int
    state: RuntimeState
    model_round: int
    tool_name: str = ""
    call_id: str = ""
    argument_handle: int = 0
    result_handle: int = 0
    error_class: str = ""


@dataclass(frozen=True)
class ExecutionProjectionV2:
    selected_tools: str
    tool_arguments: str
    tool_call_ids: str
    tool_results: str
    next_model_context: str
    handoff_targets: str
    branch_choices: str
    state_updates: str
    external_effect_sequence: str
    effect_count: int
    termination_class: str
    sanitized_final_result: str
    model_calls: int


@dataclass
class PrivateValueStore:
    _next: int = 1
    values: dict[int, bytes] = field(default_factory=dict)

    def put(self, domain: str, value: bytes) -> int:
        handle = self._next
        self._next += 1
        self.values[handle] = domain.encode("ascii") + b"\0" + bytes(value)
        return handle

    def get(self, handle: int) -> bytes:
        return self.values[handle].split(b"\0", 1)[1]


class ScriptedModel:
    """Deterministic local model boundary for exact semantic tests."""

    def __init__(self, decisions: Sequence[ModelDecision]):
        self._decisions = list(decisions)
        self.contexts: list[tuple[ContextItem, ...]] = []

    def __call__(self, agent: AgentProgramV2, context: tuple[ContextItem, ...]) -> ModelDecision:
        self.contexts.append(context)
        if not self._decisions:
            raise RuntimeError(f"no scripted decision remains for {agent.name}")
        return self._decisions.pop(0)


class AgentRuntimeV2:
    """Small trusted interpreter for bounded Agent control; heavy primitives remain adapters."""

    public_identity = "AgentControlExecutorV2"

    def __init__(self, bundle: ProgramBundleV2, models: dict[int, ModelAdapter],
                 tools: dict[str, ToolBinding]):
        self.bundle = bundle
        self.agents = bundle.by_id()
        self.models = dict(models)
        self.tools = dict(tools)
        self.private_values = PrivateValueStore()
        self.private_steps: list[PrivateStep] = []
        self._tool_results_by_call: dict[str, tuple[str, bool]] = {}

    def _step(self, agent: int, state: RuntimeState, round_index: int, **values: object) -> None:
        self.private_steps.append(PrivateStep(len(self.private_steps) + 1, agent, state,
                                              round_index, **values))

    @staticmethod
    def _context_json(context: Sequence[ContextItem]) -> str:
        return json.dumps([item.canonical() for item in context], sort_keys=True, separators=(",", ":"))

    def execute(self, initial_agent_id: int, user_input: str) -> ExecutionProjectionV2:
        if initial_agent_id not in self.agents:
            raise KeyError("initial Agent capsule is not installed")
        current = initial_agent_id
        context = [ContextItem("user", user_input)]
        selected_tools: list[str] = []
        arguments: list[dict[str, object]] = []
        call_ids: list[str] = []
        results: list[str] = []
        resumed_contexts: list[str] = []
        handoffs: list[str] = []
        updates: list[str] = []
        effects: list[dict[str, object]] = []
        model_calls = 0
        effect_count = 0
        # parent Agent, parent context, private Tool name, call ID, canonical args
        call_stack: list[tuple[int, list[ContextItem], str, str, str]] = []
        total_bound = sum(agent.max_model_rounds for agent in self.agents.values())
        for _ in range(total_bound):
            agent = self.agents[current]
            model_calls += 1
            self._step(current, RuntimeState.MODEL_READY, model_calls)
            updates.append("MODEL" if model_calls == 1 else "MODEL_RESUME")
            try:
                decision = self.models[current](agent, tuple(context))
            except Exception as exc:
                self._step(current, RuntimeState.MODEL_ERROR, model_calls,
                           error_class=type(exc).__name__)
                updates.append("MODEL_ERROR")
                return self._projection(selected_tools, arguments, call_ids, results,
                                        resumed_contexts, handoffs, updates, effects, effect_count,
                                        "MODEL_ERROR", "", model_calls)
            if decision.kind == DecisionKind.FINAL:
                if call_stack:
                    parent, parent_context, tool_name, call_id, canonical_args = call_stack.pop()
                    result_text = decision.final_text
                    result_handle = self.private_values.put("agent_tool_result", result_text.encode("utf-8"))
                    results.append(result_text)
                    parent_context.extend((
                        ContextItem("assistant_tool_call", canonical_args, call_id, tool_name),
                        ContextItem("tool", result_text, call_id, tool_name),
                    ))
                    resumed_contexts.append(self._context_json(parent_context))
                    updates.extend(("AGENT_AS_TOOL_RETURN", "MODEL_RESUME_READY"))
                    self._step(current, RuntimeState.AGENT_RETURN, model_calls,
                               tool_name=tool_name, call_id=call_id, result_handle=result_handle)
                    current = parent
                    context = parent_context
                    continue
                context.append(ContextItem("assistant", decision.final_text))
                updates.append("RETURN")
                self._step(current, RuntimeState.RETURNED, model_calls)
                return self._projection(selected_tools, arguments, call_ids, results,
                                        resumed_contexts, handoffs, updates, effects, effect_count,
                                        "RETURN", decision.final_text, model_calls)
            if decision.kind == DecisionKind.HANDOFF:
                target = agent.handoff_targets.get(decision.handoff_target)
                if target is None:
                    self._step(current, RuntimeState.MODEL_ERROR, model_calls,
                               error_class="UNRESOLVED_HANDOFF")
                    updates.append("HANDOFF_ERROR")
                    return self._projection(selected_tools, arguments, call_ids, results,
                                            resumed_contexts, handoffs, updates, effects, effect_count,
                                            "HANDOFF_ERROR", "", model_calls)
                handoffs.append(decision.handoff_target)
                updates.append("HANDOFF")
                self._step(current, RuntimeState.HANDOFF_READY, model_calls)
                handoff_id = decision.handoff_call_id or f"handoff-{model_calls}"
                context.extend((
                    ContextItem("assistant_handoff_call", "{}", handoff_id,
                                f"transfer_to_{decision.handoff_target.lower()}"),
                    ContextItem("handoff", json.dumps({"assistant": decision.handoff_target},
                                                      sort_keys=True, separators=(",", ":")),
                                handoff_id, decision.handoff_target),
                ))
                resumed_contexts.append(self._context_json(context))
                current = target
                continue
            call = decision.tool_call
            assert call is not None
            agent_tool_target = agent.agent_tool_targets.get(call.name)
            if agent_tool_target is not None:
                if agent_tool_target not in self.agents:
                    self._step(current, RuntimeState.TOOL_ERROR, model_calls,
                               tool_name=call.name, call_id=call.call_id,
                               error_class="UNRESOLVED_AGENT_TOOL")
                    updates.append("AGENT_AS_TOOL_ERROR")
                    return self._projection(selected_tools, arguments, call_ids, results,
                                            resumed_contexts, handoffs, updates, effects, effect_count,
                                            "AGENT_AS_TOOL_ERROR", "", model_calls)
                canonical_args = call.canonical_arguments()
                argument_handle = self.private_values.put("agent_tool_arguments",
                                                          canonical_args.encode("utf-8"))
                selected_tools.append(call.name)
                arguments.append(dict(call.arguments))
                call_ids.append(call.call_id)
                updates.append("AGENT_AS_TOOL_CALL")
                self._step(current, RuntimeState.AGENT_CALL_READY, model_calls,
                           tool_name=call.name, call_id=call.call_id,
                           argument_handle=argument_handle)
                call_stack.append((current, context, call.name, call.call_id, canonical_args))
                child_input = str(call.arguments.get("input", canonical_args))
                current = agent_tool_target
                context = [ContextItem("user", child_input)]
                continue
            expected_handle = agent.tool_handles.get(call.name)
            binding = self.tools.get(call.name)
            if expected_handle is None or binding is None:
                self._step(current, RuntimeState.TOOL_ERROR, model_calls,
                           tool_name=call.name, call_id=call.call_id,
                           error_class="UNKNOWN_TOOL")
                updates.append("TOOL_ERROR")
                return self._projection(selected_tools, arguments, call_ids, results,
                                        resumed_contexts, handoffs, updates, effects, effect_count,
                                        "TOOL_ERROR", "", model_calls)
            canonical_args = call.canonical_arguments()
            argument_handle = self.private_values.put("tool_arguments", canonical_args.encode("utf-8"))
            selected_tools.append(call.name)
            arguments.append(dict(call.arguments))
            call_ids.append(call.call_id)
            updates.append("TOOL_CALL")
            self._step(current, RuntimeState.TOOL_READY, model_calls, tool_name=call.name,
                       call_id=call.call_id, argument_handle=argument_handle)
            if call.call_id in self._tool_results_by_call:
                result_text, effect_happened = self._tool_results_by_call[call.call_id]
            else:
                try:
                    value = binding.invoke(dict(call.arguments))
                    result_text = str(value)
                    effect_happened = bool(binding.effectful)
                    self._tool_results_by_call[call.call_id] = (result_text, effect_happened)
                    if effect_happened:
                        effect_count += 1
                        effects.append({"tool": call.name, **dict(call.arguments)})
                except Exception as exc:
                    result_text = f"ERROR:{type(exc).__name__}"
                    effect_happened = False
                    self._tool_results_by_call[call.call_id] = (result_text, False)
                    result_handle = self.private_values.put("tool_result", result_text.encode("utf-8"))
                    results.append(result_text)
                    context.extend((ContextItem("assistant_tool_call", canonical_args, call.call_id, call.name),
                                    ContextItem("tool", result_text, call.call_id, call.name)))
                    resumed_contexts.append(self._context_json(context))
                    updates.extend(("TOOL_ERROR", "MODEL_RESUME_READY"))
                    self._step(current, RuntimeState.TOOL_ERROR, model_calls, tool_name=call.name,
                               call_id=call.call_id, argument_handle=argument_handle,
                               result_handle=result_handle, error_class=type(exc).__name__)
                    continue
            result_handle = self.private_values.put("tool_result", result_text.encode("utf-8"))
            results.append(result_text)
            context.extend((ContextItem("assistant_tool_call", canonical_args, call.call_id, call.name),
                            ContextItem("tool", result_text, call.call_id, call.name)))
            resumed_contexts.append(self._context_json(context))
            updates.extend(("TOOL_RESULT", "MODEL_RESUME_READY"))
            self._step(current, RuntimeState.MODEL_RESUME, model_calls, tool_name=call.name,
                       call_id=call.call_id, argument_handle=argument_handle,
                       result_handle=result_handle)
        self._step(current, RuntimeState.BOUND_EXCEEDED, model_calls)
        updates.append("BOUND_EXCEEDED")
        return self._projection(selected_tools, arguments, call_ids, results, resumed_contexts,
                                handoffs, updates, effects, effect_count, "BOUND_EXCEEDED", "", model_calls)

    @staticmethod
    def _projection(selected_tools: list[str], arguments: list[dict[str, object]],
                    call_ids: list[str], results: list[str], contexts: list[str],
                    handoffs: list[str], updates: list[str], effects: list[dict[str, object]],
                    effect_count: int, termination: str, final: str,
                    model_calls: int) -> ExecutionProjectionV2:
        return ExecutionProjectionV2(
            json.dumps(selected_tools), json.dumps(arguments, sort_keys=True), json.dumps(call_ids),
            json.dumps(results), json.dumps(contexts), json.dumps(handoffs), json.dumps([]),
            json.dumps(updates), json.dumps(effects, sort_keys=True), effect_count,
            termination, final, model_calls,
        )

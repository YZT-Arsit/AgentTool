from __future__ import annotations

import ast
import csv
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


COMPILED = "COMPILED"
SHARED = "SHARED_PRIMITIVE"
UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class SourceSpec:
    framework: str
    checkout: Path
    roots: tuple[Path, ...]


@dataclass(frozen=True)
class BehaviorInstance:
    framework: str
    pinned_commit: str
    relative_path: str
    line: int
    behavior_kind: str
    detail: str
    disposition: str
    reason: str


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_call_name(node.value)}.{node.attr}".strip(".")
    return ""


def _contains_control(node: ast.AST) -> bool:
    terms = ("agent", "tool", "handoff", "workflow", "run", "resume", "approval", "state", "session")
    return any(isinstance(item, (ast.Call, ast.Attribute, ast.Name)) and
               any(term in _call_name(item.func if isinstance(item, ast.Call) else item).lower() for term in terms)
               for item in ast.walk(node))


class FileVisitor(ast.NodeVisitor):
    AGENT_NAMES = {"Agent", "ChatAgent", "AIAgent", "AssistantAgent", "OpenAIAssistantAgent"}

    def __init__(self, framework: str, commit: str, relative: str):
        self.framework, self.commit, self.relative = framework, commit, relative
        self.behaviors: list[BehaviorInstance] = []
        self.counts = Counter()

    def add(self, node: ast.AST, kind: str, detail: str, disposition: str, reason: str) -> None:
        self.behaviors.append(BehaviorInstance(self.framework, self.commit, self.relative,
                                               getattr(node, "lineno", 0), kind, detail,
                                               disposition, reason))

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        short = name.rsplit(".", 1)[-1]
        lowered = name.lower()
        keywords = {item.arg: item.value for item in node.keywords if item.arg}
        if short in self.AGENT_NAMES or lowered.endswith(".as_agent"):
            self.counts["agent_constructors"] += 1
            self.add(node, "instructions", name, COMPILED,
                     "static instruction handle when literal; callable form is recorded separately")
            self.add(node, "llm", name, SHARED, "model work remains a common heavy primitive")
            self.add(node, "termination", name, COMPILED, "bounded RETURN is in the control IR")
            instructions = keywords.get("instructions")
            if instructions is not None and not isinstance(instructions, (ast.Constant, ast.JoinedStr)):
                self.counts["dynamic_instructions"] += 1
                self.add(instructions, "dynamic_instructions", ast.dump(instructions, include_attributes=False)[:160],
                         UNSUPPORTED, "arbitrary callback/expression is not a declarative template")
            for key in ("tools", "handoffs", "input_guardrails", "output_guardrails",
                        "tool_input_guardrails", "tool_output_guardrails", "mcp_servers", "middleware"):
                value = keywords.get(key)
                if value is None:
                    continue
                elements = value.elts if isinstance(value, (ast.List, ast.Tuple, ast.Set)) else [value]
                if key == "tools":
                    for element in elements:
                        self.counts["tool_instances"] += 1
                        if isinstance(element, ast.Call) and _call_name(element.func).endswith(".as_tool"):
                            self.counts["agents_as_tools"] += 1
                            self.add(element, "agents_as_tools", _call_name(element.func), UNSUPPORTED,
                                     "current IR has no exact nested-Agent-as-Tool transition")
                        else:
                            self.add(element, "tool", ast.dump(element, include_attributes=False)[:160],
                                     SHARED, "Tool execution remains a common provider primitive")
                elif key == "handoffs":
                    for element in elements:
                        self.counts["handoff_edges"] += 1
                        self.add(element, "handoff", ast.dump(element, include_attributes=False)[:160],
                                 COMPILED, "static target lowers to logical HANDOFF")
                elif "guardrail" in key:
                    for element in elements:
                        self.counts["guardrails"] += 1
                        self.add(element, "guardrail", key, UNSUPPORTED,
                                 "arbitrary native guardrail callback is not compiled")
                elif key == "mcp_servers":
                    for element in elements:
                        self.counts["mcp_invocations"] += 1
                        self.add(element, "mcp_tool_boundary", key, SHARED,
                                 "external work can use the common Tool boundary; endpoint privacy is separate")
                else:
                    for element in elements:
                        self.counts["middleware"] += 1
                        self.add(element, "middleware", key, UNSUPPORTED,
                                 "arbitrary runtime middleware is outside the declarative IR")
        if short in {"Workflow", "WorkflowBuilder", "ConcurrentBuilder", "SequentialBuilder"}:
            self.counts["workflow_instances"] += 1
            self.add(node, "workflow", name, COMPILED, "workflow identity/config is declarative")
        if short in {"function_tool", "tool"} or lowered.endswith(".function_tool"):
            self.counts["tool_instances"] += 1
            self.add(node, "tool", name, SHARED, "decorated Tool remains a common heavy primitive")
        if lowered.endswith(".as_tool"):
            self.counts["agents_as_tools"] += 1
            self.add(node, "agents_as_tools", name, UNSUPPORTED,
                     "nested Agent-as-Tool execution is not represented exactly by current IR")
        if short == "handoff":
            self.counts["handoff_edges"] += 1
            self.add(node, "handoff", name, COMPILED, "static handoff lowers to logical ID transition")
            if any(item.arg in {"input_filter", "on_handoff", "is_enabled"} for item in node.keywords):
                self.add(node, "conditional_handoff_callback", name, UNSUPPORTED,
                         "native callback/filter semantics are not compiled")
        if any(token in lowered for token in ("add_fan_out", "add_fan_in", "concurrent", "fork", "join")):
            self.counts["fanout_fanin"] += 1
            self.add(node, "fanout_fanin", name, UNSUPPORTED,
                     "parallel scheduling is not in the current one-transition IR")
        elif any(token in lowered for token in ("add_edge", "add_connection", "add_transition")):
            self.counts["workflow_edges"] += 1
            self.add(node, "workflow_edge", name, COMPILED, "static sequential edge is declarative")
        if "needs_approval" in keywords or any(token in lowered for token in ("approve", "reject", "resume", "interruption")):
            self.counts["hitl_resume"] += 1
            self.add(node, "hitl_resume", name, UNSUPPORTED,
                     "current IR lacks exact HITL_WAIT/RESUME state semantics")
        if any(token in lowered for token in ("session", "memory", "state")) and short not in self.AGENT_NAMES:
            self.counts["state_memory"] += 1
            self.add(node, "state_memory", name, UNSUPPORTED,
                     "framework-native persistence object is not automatically lowered to STATE_GET/SET")
        if "middleware" in lowered:
            self.counts["middleware"] += 1
            self.add(node, "middleware", name, UNSUPPORTED,
                     "runtime middleware remains arbitrary native code")
        if "mcp" in lowered:
            self.counts["mcp_invocations"] += 1
            self.add(node, "mcp_tool_boundary", name, SHARED,
                     "MCP work is a shared Tool primitive; endpoint privacy is not inferred")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        decorators = {_call_name(item.func if isinstance(item, ast.Call) else item).lower()
                      for item in node.decorator_list}
        if any(name.endswith(("function_tool", "tool")) for name in decorators):
            self.counts["tool_instances"] += 1
            self.add(node, "tool", node.name, SHARED, "decorated function executes behind the Tool boundary")
        if any("guardrail" in name for name in decorators):
            self.counts["guardrails"] += 1
            self.add(node, "guardrail", node.name, UNSUPPORTED,
                     "arbitrary Python guardrail body is not declarative")
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        if _contains_control(node):
            self.counts["conditional_edges"] += 1
            self.add(node, "conditional_edge", ast.unparse(node.test)[:160], UNSUPPORTED,
                     "arbitrary Python condition is not a declarative BRANCH predicate")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:
        self._visit_loop(node)

    def _visit_loop(self, node: ast.For | ast.While) -> None:
        if _contains_control(node):
            self.counts["loops"] += 1
            self.add(node, "loop", type(node).__name__, UNSUPPORTED,
                     "current IR has no proven public bounded-loop lowering")
        self.generic_visit(node)


def _commit(checkout: Path) -> str:
    return subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                                   text=True).strip()


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_corpus_audit(root: Path) -> dict[str, object]:
    if (root / "IR_V1_BASELINE_MANIFEST.json").exists():
        from corpus_audit.ir_v1_freeze import verify_frozen_baseline
        verify_frozen_baseline(root)
        raise RuntimeError(
            "IR-v1 is permanently frozen; use a new versioned IR-v2 output path on the frozen corpus."
        )
    specs = (
        SourceSpec("OpenAI Agents SDK", root / "external_stage10/openai-agents-python",
                   (Path("examples"),)),
        SourceSpec("Microsoft Agent Framework", root / "external_stage9/agent-framework",
                   (Path("python/tests/samples"), Path("python/packages/core/tests"))),
    )
    manifest: list[dict[str, object]] = []
    behaviors: list[BehaviorInstance] = []
    for spec in specs:
        commit = _commit(spec.checkout)
        paths = sorted({path for relative in spec.roots for path in (spec.checkout / relative).rglob("*.py")})
        for path in paths:
            relative = path.relative_to(spec.checkout).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            parse_error = ""
            visitor = FileVisitor(spec.framework, commit, relative)
            try:
                visitor.visit(ast.parse(text, filename=relative))
            except SyntaxError as exc:
                parse_error = f"{exc.msg}@{exc.lineno}"
            behaviors.extend(visitor.behaviors)
            counts = visitor.counts
            manifest.append({
                "framework": spec.framework, "pinned_commit": commit,
                "relative_path": relative, "bytes": len(text.encode("utf-8")),
                "parse_error": parse_error, "agent_constructors": counts["agent_constructors"],
                "workflow_instances": counts["workflow_instances"], "tool_instances": counts["tool_instances"],
                "handoff_edges": counts["handoff_edges"], "conditional_edges": counts["conditional_edges"],
                "loops": counts["loops"], "fanout_fanin": counts["fanout_fanin"],
                "agents_as_tools": counts["agents_as_tools"], "dynamic_instructions": counts["dynamic_instructions"],
                "guardrails": counts["guardrails"], "state_memory": counts["state_memory"],
                "hitl_resume": counts["hitl_resume"], "middleware": counts["middleware"],
                "mcp_tool_invocation": counts["mcp_invocations"],
                "nested_subagent_patterns": counts["agents_as_tools"] + counts["handoff_edges"],
            })

    behavior_rows = [asdict(item) for item in behaviors]
    _write_csv(root / "CORPUS_MANIFEST.csv", manifest, list(manifest[0]))
    _write_csv(root / "CORPUS_BEHAVIOR_INSTANCES.csv", behavior_rows, list(behavior_rows[0]))
    grouped: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for item in behaviors:
        for key in ((item.framework, item.behavior_kind), (item.framework, "ALL"), ("ALL", item.behavior_kind), ("ALL", "ALL")):
            grouped[key][item.disposition] += 1
    coverage_rows: list[dict[str, object]] = []
    for (framework, kind), counts in sorted(grouped.items()):
        total = sum(counts.values())
        supported = counts[COMPILED] + counts[SHARED]
        coverage_rows.append({"framework": framework, "behavior_kind": kind, "total": total,
                              "compiled": counts[COMPILED], "shared_primitive": counts[SHARED],
                              "unsupported": counts[UNSUPPORTED], "coverage": supported / total if total else 0.0})
    _write_csv(root / "CORPUS_IR_COVERAGE.csv", coverage_rows, list(coverage_rows[0]))
    overall = next(row for row in coverage_rows if row["framework"] == "ALL" and row["behavior_kind"] == "ALL")
    summary = {
        "files_scanned": len(manifest), "parse_errors": sum(bool(row["parse_error"]) for row in manifest),
        "agent_constructor_instances": sum(int(row["agent_constructors"]) for row in manifest),
        "workflow_instances": sum(int(row["workflow_instances"]) for row in manifest),
        "tool_instances": sum(int(row["tool_instances"]) for row in manifest),
        "behavior_instances": int(overall["total"]), "compiled": int(overall["compiled"]),
        "shared_primitive": int(overall["shared_primitive"]), "unsupported": int(overall["unsupported"]),
        "coverage": float(overall["coverage"]),
    }
    return summary

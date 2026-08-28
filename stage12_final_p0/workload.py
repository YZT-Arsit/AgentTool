from __future__ import annotations

import ast
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TAU_COMMIT = "a2c024725189473d2d7cea3a5cfdbcc67478e41f"
AGENTDOJO_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"


@dataclass(frozen=True)
class PublicTask:
    workload_id: str
    source: str
    source_commit: str
    domain: str
    source_task_id: str
    public_task: str
    effect_type: str
    effect_arguments_json: str
    reference_steps: int
    mediation_families: str = "AUTHORIZATION|PROVENANCE_HISTORY"
    private_configurations: int = 4


MUTATING = (
    "send", "create", "delete", "update", "schedule", "transfer", "book",
    "cancel", "exchange", "return", "share", "add", "remove", "pay",
)


def _is_mutating(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in MUTATING)


def _tau_tasks(limit: int = 20) -> list[PublicTask]:
    rows: list[PublicTask] = []
    for domain in ("retail", "airline"):
        path = ROOT / "external_stage12" / "tau2-bench" / "data" / "tau2" / "domains" / domain / "tasks.json"
        tasks = json.loads(path.read_text(encoding="utf-8"))
        for task in tasks:
            actions = task.get("evaluation_criteria", {}).get("actions") or []
            mutating = [action for action in actions if _is_mutating(action["name"])]
            if not mutating:
                continue
            effect = mutating[-1]
            instructions = task["user_scenario"]["instructions"]
            public = instructions.get("reason_for_call") or instructions.get("task_instructions") or f"{domain} task {task['id']}"
            rows.append(PublicTask(
                f"tau2-{domain}-{task['id']}", "tau2-bench", TAU_COMMIT, domain, str(task["id"]),
                " ".join(str(public).split()), effect["name"],
                json.dumps(effect.get("arguments") or {}, sort_keys=True), len(actions),
            ))
            if len(rows) >= limit:
                return rows
    return rows


def _class_constants(node: ast.ClassDef) -> dict[str, object]:
    constants: dict[str, object] = {}
    for item in node.body:
        if isinstance(item, (ast.Assign, ast.AnnAssign)):
            target = item.targets[0] if isinstance(item, ast.Assign) else item.target
            value = item.value
            if isinstance(target, ast.Name) and value is not None:
                try:
                    constants[target.id] = ast.literal_eval(value)
                except Exception:
                    pass
    return constants


def _eval_public(node: ast.AST, constants: dict[str, object]) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        if node.attr in constants:
            return constants[node.attr]
    if isinstance(node, ast.List):
        return [_eval_public(x, constants) for x in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_public(x, constants) for x in node.elts)
    if isinstance(node, ast.Dict):
        return {_eval_public(k, constants): _eval_public(v, constants) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                parts.append(str(_eval_public(value.value, constants)))
        return "".join(parts)
    raise ValueError(ast.dump(node, include_attributes=False))


def _agentdojo_tasks(limit: int = 20) -> list[PublicTask]:
    rows: list[PublicTask] = []
    base = ROOT / "external_stage12" / "agentdojo" / "src" / "agentdojo" / "default_suites" / "v1"
    for domain in ("workspace", "slack", "banking", "travel"):
        path = base / domain / "user_tasks.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for cls in (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name.startswith("UserTask")):
            constants = _class_constants(cls)
            prompt = constants.get("PROMPT")
            if prompt is None:
                for item in cls.body:
                    if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PROMPT" for t in item.targets):
                        try:
                            prompt = _eval_public(item.value, constants)
                        except Exception:
                            prompt = f"AgentDojo {domain} {cls.name}"
            calls: list[tuple[str, object]] = []
            for call in (node for node in ast.walk(cls) if isinstance(node, ast.Call)):
                func_name = None
                if isinstance(call.func, ast.Name):
                    func_name = call.func.id
                if func_name != "FunctionCall":
                    continue
                kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg}
                try:
                    name = str(_eval_public(kwargs["function"], constants))
                except Exception:
                    continue
                try:
                    args = _eval_public(kwargs["args"], constants)
                except Exception:
                    args = {"source_expression": ast.unparse(kwargs.get("args", ast.Dict(keys=[], values=[])))}
                calls.append((name, args))
            mutating = [call for call in calls if _is_mutating(call[0])]
            if not mutating:
                continue
            effect_name, effect_args = mutating[-1]
            rows.append(PublicTask(
                f"agentdojo-{domain}-{cls.name}", "AgentDojo", AGENTDOJO_COMMIT,
                domain, cls.name, " ".join(str(prompt or f"AgentDojo {domain} {cls.name}").split()),
                effect_name, json.dumps(effect_args, sort_keys=True, default=str), len(calls),
            ))
            if len(rows) >= limit:
                return rows
    return rows


def build_workload(output: Path) -> list[PublicTask]:
    tasks = _tau_tasks(20) + _agentdojo_tasks(20)
    if len(tasks) != 40:
        raise AssertionError(f"expected 40 public-derived tasks, found {len(tasks)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(tasks[0])))
        writer.writeheader()
        writer.writerows(asdict(task) for task in tasks)
    return tasks


def load_workload(path: Path) -> list[PublicTask]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [PublicTask(**{**row, "reference_steps": int(row["reference_steps"]), "private_configurations": int(row["private_configurations"])}) for row in csv.DictReader(handle)]

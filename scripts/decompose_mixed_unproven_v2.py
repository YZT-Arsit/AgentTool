from __future__ import annotations

import ast
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corpus_audit.ir_v1_freeze import verify_frozen_baseline

BUCKET = "MIXED_OR_BOUND_NOT_PROVEN"
SUBCLASSES = (
    "SOURCE_TRACEABLE_BOUNDED",
    "FRAMEWORK_CONTRACT_BOUNDED",
    "GENUINELY_DYNAMIC",
    "EXTRACTOR_AMBIGUOUS",
)


def source_path(row: dict[str, str]) -> Path:
    checkout = (ROOT / "external_stage10/openai-agents-python" if row["framework"] == "OpenAI Agents SDK"
                else ROOT / "external_stage9/agent-framework")
    return checkout / row["relative_path"]


def node_at_line(path: Path, line: int) -> ast.AST | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None
    candidates = [node for node in ast.walk(tree) if getattr(node, "lineno", -1) == line]
    # Classification needs the source construct, not a child Name/attribute that
    # happens to share its first line. Prefer the enclosing statement, then Call.
    statements = [node for node in candidates if isinstance(node, ast.stmt)]
    if statements:
        return min(statements, key=lambda node: len(list(ast.walk(node))))
    calls = [node for node in candidates if isinstance(node, ast.Call)]
    if calls:
        return min(calls, key=lambda node: len(list(ast.walk(node))))
    return min(candidates, key=lambda node: len(list(ast.walk(node))), default=None)


def literal_bounded_iteration(node: ast.AST | None) -> bool:
    if not isinstance(node, (ast.For, ast.AsyncFor)):
        return False
    iterator = node.iter
    if isinstance(iterator, (ast.List, ast.Tuple, ast.Set)):
        return True
    return (isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Name) and
            iterator.func.id == "range" and iterator.args and
            all(isinstance(arg, ast.Constant) and isinstance(arg.value, int) for arg in iterator.args))


def classify(row: dict[str, str]) -> tuple[str, str]:
    kind, detail, excerpt = row["behavior_kind"], row["detail"].lower(), row["source_excerpt"].lower()
    node = node_at_line(source_path(row), int(row["line"]))
    if kind == "dynamic_instructions":
        return "GENUINELY_DYNAMIC", "instruction value is a runtime expression/callback"
    if kind == "loop":
        if literal_bounded_iteration(node):
            return "SOURCE_TRACEABLE_BOUNDED", "literal/range loop bound is visible in source"
        if isinstance(node, (ast.While, ast.AsyncFor)) or "while " in excerpt:
            return "GENUINELY_DYNAMIC", "runtime termination or async input controls iteration"
        return "EXTRACTOR_AMBIGUOUS", "static extractor did not establish a finite source bound"
    if kind == "fanout_fanin":
        if node is not None and any(isinstance(value, (ast.List, ast.Tuple)) for value in ast.walk(node)):
            return "SOURCE_TRACEABLE_BOUNDED", "fan-out width is represented by a literal source collection"
        return "FRAMEWORK_CONTRACT_BOUNDED", "framework combinator is structured but runtime width/order is not source-proven"
    if kind == "agents_as_tools":
        if ".as_tool" in excerpt and not any(token in excerpt for token in ("lambda", "input_builder", "stream_callback")):
            return "SOURCE_TRACEABLE_BOUNDED", "static target and call site are source-visible; recursive depth remains a separate profile bound"
        return "FRAMEWORK_CONTRACT_BOUNDED", "Agent-as-Tool has a framework call/return contract but optional callbacks remain"
    if kind == "hitl_resume":
        if any(token in detail for token in ("approve", "reject", "resume", "interruption")):
            return "FRAMEWORK_CONTRACT_BOUNDED", "explicit HITL state transition has a framework-defined record contract"
        return "EXTRACTOR_AMBIGUOUS", "name heuristic found HITL-like behavior without a proven transition contract"
    if kind == "state_memory":
        dynamic_backends = ("sqlite", "redis", "mongo", "dapr", "openai", "file", "path", "exec", "call_tool")
        state_ops = (".get", ".set", ".has", ".exists", ".delete", ".discard", "get_state", "set_state")
        contract_terms = ("agentsession", "sessioncontext", "checkpoint", "memor", "state", "session")
        if any(token in detail for token in dynamic_backends):
            return "GENUINELY_DYNAMIC", "external/durable backend or runtime I/O controls state semantics"
        if any(token in detail for token in state_ops) and isinstance(node, ast.Call):
            if node.args and isinstance(node.args[0], ast.Constant):
                return "SOURCE_TRACEABLE_BOUNDED", "structured state operation uses a literal source key"
            return "FRAMEWORK_CONTRACT_BOUNDED", "structured state operation has a contract but dynamic key/value"
        if any(token in detail for token in contract_terms) and isinstance(node, ast.Call):
            return "FRAMEWORK_CONTRACT_BOUNDED", "recognized framework state/session constructor or transition API"
        return "EXTRACTOR_AMBIGUOUS", "broad name heuristic does not establish protected state semantics"
    return "EXTRACTOR_AMBIGUOUS", "no sound subclass rule for this source instance"


def main() -> None:
    verify_frozen_baseline(ROOT)
    output = ROOT / "MIXED_UNPROVEN_DECOMPOSITION_V2.csv"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite decomposition: {output}")
    with (ROOT / "IR_V1_UNSUPPORTED_INSTANCE_AUDIT.csv").open(newline="", encoding="utf-8") as handle:
        source = [row for row in csv.DictReader(handle) if row["semantic_bucket"] == BUCKET]
    rows = []
    for row in source:
        subclass, basis = classify(row)
        rows.append({
            "framework": row["framework"], "pinned_commit": row["pinned_commit"],
            "relative_path": row["relative_path"], "line": row["line"],
            "behavior_kind": row["behavior_kind"], "detail": row["detail"],
            "mixed_subclass": subclass, "classification_basis": basis,
            "source_excerpt": row["source_excerpt"],
            "implemented_and_semantically_tested": "NO",
            "coverage_gain_claimed": "NO",
        })
    if len(rows) != 1904:
        raise AssertionError(f"frozen MIXED/UNPROVEN denominator changed: {len(rows)}")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    counts = Counter(row["mixed_subclass"] for row in rows)
    by_family: dict[str, Counter] = defaultdict(Counter)
    by_framework: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_family[row["behavior_kind"]][row["mixed_subclass"]] += 1
        by_framework[row["framework"]][row["mixed_subclass"]] += 1
    summary = {
        "denominator": len(rows), "subclass_counts": counts,
        "family_counts": {key: value for key, value in sorted(by_family.items())},
        "framework_counts": {key: value for key, value in sorted(by_framework.items())},
        "interpretation": "semantic triage only; no instance changes IR-v1 or IR-v2 coverage",
    }
    (ROOT / "MIXED_UNPROVEN_DECOMPOSITION_V2.json").write_text(
        json.dumps(summary, indent=2, default=dict) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, default=dict))


if __name__ == "__main__":
    main()

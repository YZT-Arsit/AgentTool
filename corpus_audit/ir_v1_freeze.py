from __future__ import annotations

import ast
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


IR_V1_FILES = {
    "CORPUS_MANIFEST.csv": "028B01769C7DC7CA6E687917C24A4F284B79367191EE73F6445DD6231F3F1010",
    "CORPUS_BEHAVIOR_INSTANCES.csv": "1D71E0D508F158D2A01420062CFBB73016381F2BBD5417C2EA5F121A4CD117F7",
    "CORPUS_IR_COVERAGE.csv": "59E136A549C5EA3C78904BC543656D111FFBFA83D282CC34041CBBABC04C6A6A",
    "CORPUS_IR_AUDIT.md": "BFE65DE3D18648F63BD5FFB19A40A5CFEDAD1BD0BF2D9748199EE452E6F92E85",
    "SEMANTIC_FIDELITY_RESULTS.csv": "2CA0418692DDD7D84B17615807B929FC4021CCBAA99103A1891971D2FC7A5E74",
    "SEMANTIC_FAILURE_CASES.csv": "D95CB736D2826E2193A7928C03211A1C66EC908BD0BDEC6DFB05D62D102FA235",
}

EXPECTED = {
    "files": 314,
    "behavior_instances": 7386,
    "compiled": 1708,
    "shared_primitive": 1866,
    "unsupported": 3812,
    "coverage": 0.4838884375846195,
}

CHECKOUTS = {
    "OpenAI Agents SDK": {
        "path": "external_stage10/openai-agents-python",
        "commit": "a40ae9803e6b7a79faa246293f56adb100d5868b",
        "roots": ("examples",),
    },
    "Microsoft Agent Framework": {
        "path": "external_stage9/agent-framework",
        "commit": "af461de51da16f5cb800ff7febc0f8f96355607a",
        "roots": ("python/tests/samples", "python/packages/core/tests"),
    },
}

STRUCTURED = "STRUCTURED_BOUNDED_CANDIDATE"
ARBITRARY = "ARBITRARY_CALLBACK_OR_RUNTIME"
MIXED = "MIXED_OR_BOUND_NOT_PROVEN"
ARTIFACT = "EXTRACTOR_FALSE_POSITIVE_OR_OUT_OF_SCOPE"


FAMILY_DECISIONS = {
    "agents_as_tools": (
        "PARTIAL_SUBSET",
        "AGENT_AS_TOOL_CALL/RETURN, a bounded nested-capsule stack, and a protected argument/result ABI",
        "The wrapper is recognizable, but exact semantics require the nested Agent control plane to compile and bound independently.",
    ),
    "conditional_edge": (
        "PARTIAL_SUBSET",
        "typed side-effect-free predicate bytecode plus BRANCH",
        "Literal/comparison predicates can plausibly lower exactly; arbitrary calls and Python truth evaluation cannot.",
    ),
    "conditional_handoff_callback": (
        "NO_GENERAL_EXACT_LOWERING",
        "a declarative handoff-filter predicate subset; otherwise a trusted native callback boundary",
        "The observed callbacks/filters may execute arbitrary framework or Python code.",
    ),
    "dynamic_instructions": (
        "NO_GENERAL_EXACT_LOWERING",
        "bounded instruction templates with typed context selectors; otherwise a trusted native callback boundary",
        "Dynamic instructions can be arbitrary computations with external state and effects.",
    ),
    "fanout_fanin": (
        "PARTIAL_SUBSET",
        "FORK/JOIN/PARALLEL_GROUP with a public maximum width, ordering, cancellation, and reducer semantics",
        "Static fan-out lists are structured; dynamic membership, scheduling, and reducers need stronger semantics.",
    ),
    "guardrail": (
        "NO_GENERAL_EXACT_LOWERING",
        "typed declarative policy predicates for a restricted subset; otherwise a trusted native guardrail boundary",
        "Framework guardrails are callable application code, not merely Boolean expressions.",
    ),
    "hitl_resume": (
        "PARTIAL_SUBSET",
        "HITL_WAIT/HITL_RESUME with durable continuation, approval token, rejection, and cancellation semantics",
        "The protocol is structured when approval configuration and continuation points are static; callback policy remains arbitrary.",
    ),
    "loop": (
        "PARTIAL_SUBSET",
        "public-bounded LOOP with an explicit counter, break/continue, and failure semantics",
        "Literal bounded iteration is structured; data-dependent and callback-driven loops are not proven bounded.",
    ),
    "middleware": (
        "NO_GENERAL_EXACT_LOWERING",
        "stage-specific declarative hook opcodes for restricted middleware; otherwise a trusted native middleware boundary",
        "Middleware may intercept, mutate, retry, persist, or perform arbitrary I/O across the runtime.",
    ),
    "state_memory": (
        "PARTIAL_SUBSET",
        "typed STATE_GET/SET/APPEND/CAS with session, version, transaction, and failure semantics",
        "The API calls are recognizable, but exact framework persistence and object behavior are not captured by IR-v1.",
    ),
}


@dataclass(frozen=True)
class ClassifiedInstance:
    framework: str
    pinned_commit: str
    relative_path: str
    line: int
    behavior_kind: str
    detail: str
    ir_v1_disposition: str
    semantic_bucket: str
    exact_lowering_feasibility: str
    required_ir_primitive: str
    classification_basis: str
    source_excerpt: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: Iterable[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def verify_frozen_baseline(root: Path) -> dict[str, str]:
    observed = {name: sha256(root / name) for name in IR_V1_FILES}
    mismatches = {name: {"expected": IR_V1_FILES[name], "observed": value}
                  for name, value in observed.items() if value != IR_V1_FILES[name]}
    if mismatches:
        raise RuntimeError(
            "IR-v1 baseline is frozen and may not be overwritten or reinterpreted: "
            + json.dumps(mismatches, sort_keys=True)
        )
    return observed


def _source_path(root: Path, framework: str, relative_path: str) -> Path:
    return root / str(CHECKOUTS[framework]["path"]) / relative_path


def _node_at_line(tree: ast.AST, line: int, classes: tuple[type[ast.AST], ...]) -> ast.AST | None:
    nodes = [node for node in ast.walk(tree) if isinstance(node, classes)
             and getattr(node, "lineno", -1) == line]
    return min(nodes, key=lambda node: getattr(node, "end_lineno", line) - line) if nodes else None


def _contains_arbitrary_execution(node: ast.AST | None) -> bool:
    if node is None:
        return True
    forbidden = (ast.Call, ast.Await, ast.Lambda, ast.NamedExpr, ast.Yield, ast.YieldFrom,
                 ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    return any(isinstance(child, forbidden) for child in ast.walk(node))


def _literal_bounded_loop(node: ast.AST | None) -> bool:
    if isinstance(node, ast.For):
        iterator = node.iter
        if isinstance(iterator, (ast.List, ast.Tuple, ast.Set)):
            return all(isinstance(item, ast.Constant) for item in iterator.elts)
        if isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Name) and iterator.func.id == "range":
            return bool(iterator.args) and all(isinstance(item, ast.Constant) and isinstance(item.value, int)
                                               for item in iterator.args)
    return False


def _call_is_static_fanout(node: ast.AST | None) -> bool:
    if not isinstance(node, ast.Call):
        return False
    arguments = list(node.args) + [item.value for item in node.keywords]
    containers = [item for item in arguments if isinstance(item, (ast.List, ast.Tuple, ast.Set))]
    return bool(containers) and all(not _contains_arbitrary_execution(item) for item in containers)


def _hitl_is_static(node: ast.AST | None) -> bool:
    if not isinstance(node, ast.Call):
        return False
    name = ast.unparse(node.func).lower()
    if any(token in name for token in ("approve", "reject", "resume", "interruption")):
        return True
    for keyword in node.keywords:
        if keyword.arg == "needs_approval" and isinstance(keyword.value, ast.Constant):
            return isinstance(keyword.value.value, bool)
    return False


def _call_name(node: ast.AST | None) -> str:
    if not isinstance(node, ast.Call):
        return ""
    try:
        return ast.unparse(node.func).lower()
    except Exception:
        return ""


def classify_instance(kind: str, node: ast.AST | None, detail: str) -> tuple[str, str]:
    lowered_detail = detail.lower()
    if kind in {"guardrail", "middleware", "conditional_handoff_callback"}:
        return ARBITRARY, "Family admits arbitrary callbacks/runtime code; no source-local bound was assumed."
    if kind == "dynamic_instructions":
        if isinstance(node, (ast.Call, ast.Lambda)) or lowered_detail.startswith(("call(", "lambda(")):
            return ARBITRARY, "Instruction construction invokes arbitrary runtime computation."
        return MIXED, "A referenced instruction value may be a static template or a callback; the frozen extractor did not resolve it."
    if kind in {"agents_as_tools", "state_memory"}:
        return MIXED, "The surface API is structured, but exact nested/runtime semantics are not represented or proven bounded."
    if kind == "conditional_edge":
        predicate = node.test if isinstance(node, ast.If) else node
        try:
            rendered = ast.unparse(predicate)
        except Exception:
            rendered = ""
        if rendered in {"__name__ == '__main__'", '__name__ == "__main__"'}:
            return ARTIFACT, "Module-entry boilerplate was lexically counted because its body invokes Agent control."
        if not _contains_arbitrary_execution(predicate):
            return STRUCTURED, "Source predicate contains no call, lambda, await, yield, or comprehension."
        return ARBITRARY, "Source predicate invokes or embeds arbitrary runtime computation."
    if kind == "loop":
        if _literal_bounded_loop(node):
            return STRUCTURED, "Source loop has a literal finite iterable or literal-integer range bound."
        return MIXED, "No public literal iteration bound is established by the source-local syntax."
    if kind == "fanout_fanin":
        name = _call_name(node)
        explicit = any(token in name for token in ("add_fan_out", "add_fan_in", "concurrentbuilder", "concurrentprocessor"))
        runtime_concurrency = any(token in name for token in ("concurrent.futures", "_run_concurrently"))
        if not explicit and not runtime_concurrency:
            return ARTIFACT, "The frozen substring detector matched a non-Agent join/fork name rather than a fan-out/fan-in control primitive."
        if explicit and _call_is_static_fanout(node):
            return STRUCTURED, "Fan-out call contains an explicit static target container without nested execution."
        if runtime_concurrency:
            return ARBITRARY, "General runtime concurrency is not a declarative Agent fan-out/fan-in graph."
        return MIXED, "Fan-out membership or concurrency semantics are not source-locally fixed."
    if kind == "hitl_resume":
        if _hitl_is_static(node):
            return STRUCTURED, "Approval/resume operation or approval requirement is syntactically explicit."
        return MIXED, "Approval policy or continuation semantics are not source-locally fixed."
    raise ValueError(f"unclassified unsupported family: {kind}")


def _classify_unsupported(root: Path) -> list[ClassifiedInstance]:
    rows = [row for row in read_csv(root / "CORPUS_BEHAVIOR_INSTANCES.csv")
            if row["disposition"] == "UNSUPPORTED"]
    cache: dict[Path, tuple[list[str], ast.AST | None]] = {}
    results: list[ClassifiedInstance] = []
    for row in rows:
        path = _source_path(root, row["framework"], row["relative_path"])
        if path not in cache:
            text = path.read_text(encoding="utf-8", errors="replace")
            try:
                tree: ast.AST | None = ast.parse(text, filename=str(path))
            except SyntaxError:
                tree = None
            cache[path] = (text.splitlines(), tree)
        lines, tree = cache[path]
        line = int(row["line"])
        kind = row["behavior_kind"]
        classes: tuple[type[ast.AST], ...]
        if kind == "conditional_edge":
            classes = (ast.If,)
        elif kind == "loop":
            classes = (ast.For, ast.While)
        else:
            classes = (ast.Call, ast.FunctionDef, ast.AsyncFunctionDef, ast.Name, ast.Attribute)
        node = _node_at_line(tree, line, classes) if tree is not None else None
        bucket, basis = classify_instance(kind, node, row["detail"])
        feasibility, primitive, _ = FAMILY_DECISIONS[kind]
        excerpt = lines[line - 1].strip() if 0 < line <= len(lines) else ""
        results.append(ClassifiedInstance(
            row["framework"], row["pinned_commit"], row["relative_path"], line, kind,
            row["detail"], row["disposition"], bucket, feasibility, primitive, basis, excerpt,
        ))
    return results


def _membership_digest(rows: list[dict[str, str]]) -> str:
    encoded = "\n".join(sorted(f"{row['framework']}|{row['pinned_commit']}|{row['relative_path']}"
                                for row in rows)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def generate_file_inclusion_audit(root: Path, manifest: list[dict[str, str]]) -> dict[str, object]:
    included = {(row["framework"], row["relative_path"]) for row in manifest}
    rows: list[dict[str, object]] = []
    for framework, spec in CHECKOUTS.items():
        checkout = root / str(spec["path"])
        for path in sorted(item for item in checkout.rglob("*.py") if ".git" not in item.parts):
            relative = path.relative_to(checkout).as_posix()
            is_included = (framework, relative) in included
            if is_included:
                if framework == "OpenAI Agents SDK":
                    rule, reason = "PINNED_EXAMPLE_ROOT", "INCLUDED_OPENAI_EXAMPLE"
                elif relative.startswith("python/tests/samples/"):
                    rule, reason = "PINNED_SAMPLE_TEST_ROOT", "INCLUDED_MICROSOFT_SAMPLE_TEST"
                else:
                    rule, reason = "SPARSE_CHECKOUT_BEHAVIORAL_TEST_CORPUS", "INCLUDED_MICROSOFT_CORE_BEHAVIOR_TEST"
            elif "/src/" in f"/{relative}" or relative.startswith("src/") or "/packages/" in f"/{relative}" and "/tests/" not in f"/{relative}":
                rule, reason = "EXCLUDED", "FRAMEWORK_IMPLEMENTATION_NOT_EXAMPLE"
            elif framework == "OpenAI Agents SDK" and relative.startswith("tests/"):
                rule, reason = "EXCLUDED", "FRAMEWORK_TEST_NOT_SELECTED_EXAMPLE_CORPUS"
            else:
                rule, reason = "EXCLUDED", "OUTSIDE_FROZEN_IR_V1_CORPUS_ROOT"
            rows.append({
                "framework": framework,
                "pinned_commit": spec["commit"],
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "discovered_materialized_python_file": "YES",
                "included_ir_v1": "YES" if is_included else "NO",
                "inclusion_rule": rule,
                "exclusion_reason": "" if is_included else reason,
            })
    observed_included = {(str(row["framework"]), str(row["relative_path"]))
                         for row in rows if row["included_ir_v1"] == "YES"}
    if observed_included != included:
        raise RuntimeError(f"file-audit membership mismatch: missing={included-observed_included}, extra={observed_included-included}")
    write_csv(root / "CORPUS_FILE_INCLUSION_AUDIT.csv", rows, rows[0].keys())
    return {
        "discovered": len(rows),
        "included": sum(row["included_ir_v1"] == "YES" for row in rows),
        "excluded": sum(row["included_ir_v1"] == "NO" for row in rows),
        "by_framework": {
            framework: {
                "discovered": sum(row["framework"] == framework for row in rows),
                "included": sum(row["framework"] == framework and row["included_ir_v1"] == "YES" for row in rows),
                "excluded": sum(row["framework"] == framework and row["included_ir_v1"] == "NO" for row in rows),
            } for framework in CHECKOUTS
        },
        "exclusion_reasons": dict(Counter(str(row["exclusion_reason"]) for row in rows if row["exclusion_reason"])),
    }


def generate_ir_v1_freeze(root: Path) -> dict[str, object]:
    hashes = verify_frozen_baseline(root)
    manifest = read_csv(root / "CORPUS_MANIFEST.csv")
    coverage = read_csv(root / "CORPUS_IR_COVERAGE.csv")
    overall = next(row for row in coverage if row["framework"] == "ALL" and row["behavior_kind"] == "ALL")
    observed = {
        "files": len(manifest),
        "behavior_instances": int(overall["total"]),
        "compiled": int(overall["compiled"]),
        "shared_primitive": int(overall["shared_primitive"]),
        "unsupported": int(overall["unsupported"]),
        "coverage": float(overall["coverage"]),
    }
    if observed != EXPECTED:
        raise RuntimeError(f"IR-v1 baseline totals changed: expected={EXPECTED}, observed={observed}")
    freeze = {
        "baseline_id": "IR-v1",
        "status": "PERMANENTLY_FROZEN",
        "coverage_display": "48.39%",
        "coverage_exact": EXPECTED["coverage"],
        "counts": EXPECTED,
        "corpus_membership_sha256": _membership_digest(manifest),
        "source_checkouts": CHECKOUTS,
        "artifact_sha256": hashes,
        "rules": [
            "Unsupported IR-v1 instances must never be relabeled in place.",
            "IR-v2 must be evaluated as a new version on exactly this corpus membership.",
            "No projected coverage is implied by feasibility classifications.",
            "Dynamic fidelity continuation is separate from static corpus coverage.",
        ],
    }
    (root / "IR_V1_BASELINE_MANIFEST.json").write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")

    classified = _classify_unsupported(root)
    instance_rows = [asdict(item) for item in classified]
    write_csv(root / "IR_V1_UNSUPPORTED_INSTANCE_AUDIT.csv", instance_rows, instance_rows[0].keys())
    by_family: dict[str, list[ClassifiedInstance]] = defaultdict(list)
    for item in classified:
        by_family[item.behavior_kind].append(item)
    pareto: list[dict[str, object]] = []
    cumulative = 0
    for family, instances in sorted(by_family.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        cumulative += len(instances)
        feasibility, primitive, note = FAMILY_DECISIONS[family]
        pareto.append({
            "rank": len(pareto) + 1,
            "behavior_family": family,
            "unsupported_instances": len(instances),
            "percent_of_all_unsupported": len(instances) / EXPECTED["unsupported"],
            "cumulative_instances": cumulative,
            "cumulative_percent": cumulative / EXPECTED["unsupported"],
            "source_files": len({(item.framework, item.relative_path) for item in instances}),
            "openai_instances": sum(item.framework == "OpenAI Agents SDK" for item in instances),
            "openai_source_files": len({item.relative_path for item in instances if item.framework == "OpenAI Agents SDK"}),
            "microsoft_instances": sum(item.framework == "Microsoft Agent Framework" for item in instances),
            "microsoft_source_files": len({item.relative_path for item in instances if item.framework == "Microsoft Agent Framework"}),
            "structured_bounded_candidates": sum(item.semantic_bucket == STRUCTURED for item in instances),
            "arbitrary_callback_or_runtime": sum(item.semantic_bucket == ARBITRARY for item in instances),
            "mixed_or_bound_not_proven": sum(item.semantic_bucket == MIXED for item in instances),
            "extractor_false_positive_or_out_of_scope": sum(item.semantic_bucket == ARTIFACT for item in instances),
            "exact_lowering_feasibility": feasibility,
            "required_ir_primitive": primitive,
            "feasibility_boundary": note,
        })
    write_csv(root / "IR_V1_UNSUPPORTED_PARETO.csv", pareto, pareto[0].keys())

    examples: list[dict[str, object]] = []
    for family, instances in sorted(by_family.items()):
        selected: list[ClassifiedInstance] = []
        for framework in CHECKOUTS:
            framework_items = [item for item in instances if item.framework == framework]
            distinct: set[tuple[str, int]] = set()
            for item in framework_items:
                key = (item.relative_path, item.line)
                if key in distinct:
                    continue
                selected.append(item)
                distinct.add(key)
                if len(distinct) == 3:
                    break
        for item in selected:
            examples.append({
                "behavior_family": family,
                "framework": item.framework,
                "pinned_commit": item.pinned_commit,
                "relative_path": item.relative_path,
                "line": item.line,
                "semantic_bucket": item.semantic_bucket,
                "source_excerpt": item.source_excerpt,
                "detail": item.detail,
            })
    write_csv(root / "IR_V1_UNSUPPORTED_EXAMPLES.csv", examples, examples[0].keys())
    file_audit = generate_file_inclusion_audit(root, manifest)
    return {"freeze": freeze, "pareto": pareto, "file_audit": file_audit,
            "semantic_buckets": dict(Counter(item.semantic_bucket for item in classified))}

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from canonical_v9.runner import GO_RUNNER
from v10_1_executor.registry import REGISTRY, eligible_adapter, registry_json


OLD_SEMANTIC = ROOT / "CANONICAL_SEMANTIC_HOLDOUT_V10_FREEZE.json"
OLD_STRUCTURAL = ROOT / "STRUCTURAL_SIZE_HOLDOUT_V10_FREEZE.json"
V9_FREEZE = ROOT / "V9_CANONICAL_FUNCTIONAL_FREEZE.json"
CORPUS = ROOT / "ACTION_MEDIATION_CORPUS_V6.csv"
PROFILE = ROOT / "PUBLIC_PROFILE_V10.json"
OLD_EXPECTED_HASHES = {
    OLD_SEMANTIC.name: "6699fe315ab35ab059c7e2e44e09f24a36ed07b047c1646d491f2daacaf10f9d",
    OLD_STRUCTURAL.name: "2022c655161d339a2751637f997fa62a68c0bc600427d5d4adf9a17281a72827",
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def assert_old_manifests_untouched() -> tuple[dict[str, Any], dict[str, Any]]:
    for path in (OLD_SEMANTIC, OLD_STRUCTURAL):
        if sha(path) != OLD_EXPECTED_HASHES[path.name]:
            raise AssertionError(f"old V10A manifest changed: {path.name}")
    semantic = json.loads(OLD_SEMANTIC.read_text(encoding="utf-8"))
    structural = json.loads(OLD_STRUCTURAL.read_text(encoding="utf-8"))
    if semantic["selected_holdout_executed"] or structural["selected_holdout_executed"]:
        raise AssertionError("old V10A manifest claims selected execution")
    return semantic, structural


def site_key(framework: str, path: str, line: int | str) -> str:
    return f"{framework}|{path}|{int(line)}"


def normalize_source_path(framework: str, value: str) -> str:
    path = value.replace("\\", "/")
    prefixes = (
        "external_stage10/openai-agents-python/",
        "external_stage9/agent-framework/",
    )
    for prefix in prefixes:
        if path.startswith(prefix):
            path = path[len(prefix):]
    return path


def historical_semantic_sites(old_semantic: dict[str, Any]) -> tuple[set[str], list[dict[str, Any]]]:
    keys: set[str] = set()
    reasons: list[dict[str, Any]] = []
    historical_csvs = {
        *ROOT.glob("ACTION_SEMANTIC_HOLDOUT_V*.csv"),
        ROOT / "SEMANTIC_FIDELITY_RESULTS.csv",
        ROOT / "SEMANTIC_FIDELITY_V2_DEVELOPMENT_REGRESSION_20260828.csv",
        ROOT / "SEMANTIC_FIDELITY_V2_RESULTS.csv",
        ROOT / "SEMANTIC_HOLDOUT_V2_RESULTS.csv",
        ROOT / "SEMANTIC_HOLDOUT_V3_RESULTS.csv",
        ROOT / "IR_V1_DYNAMIC_FIDELITY_CONTINUATION.csv",
    }
    for path in sorted(item for item in historical_csvs if item.is_file()):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                framework = row.get("framework", "")
                source = normalize_source_path(framework, row.get("source_path", ""))
                if not framework or not source:
                    continue
                # Older evidence does not always preserve source line. Exclude
                # the whole file in that case; this is deliberately conservative.
                key = f"{framework}|{source}|*"
                keys.add(key)
                reasons.append({"kind": "SEMANTIC_SOURCE_FILE", "key": key, "reason": path.name})
    for case in old_semantic["cases"]:
        source = case["source"]
        key = site_key(case["framework"], source["path"], source["line"])
        keys.add(key)
        reasons.append({"kind": "V10A_SEMANTIC_SOURCE_SITE", "key": key, "case_id": case["case_id"], "reason": "FROZEN_BUT_NOT_EXECUTED_SUPERSEDED_V10A"})
    return keys, reasons


def structural_sequence_signature_from_parts(agent_id: int, agent_capability: str, actions: list[dict[str, Any]]) -> str:
    protected = {
        "private_agent_id": agent_id,
        "private_agent_capability": agent_capability,
        "private_actions": [
        {
            "action_kind": item["action_kind"],
            "capability": item["capability"],
            "effect_semantics": item["effect_semantics"],
            "protected_argument": item["protected_argument"],
        }
        for item in actions
        ],
    }
    return sha_bytes(canonical_json(protected))


def structural_sequence_signature(arm: dict[str, Any]) -> str:
    return structural_sequence_signature_from_parts(
        int(arm["private_agent_id"]), str(arm["private_agent_capability"]), list(arm["private_actions"])
    )


def create_supersession_audit(old_semantic: dict[str, Any], old_structural: dict[str, Any], exclusions: list[dict[str, Any]]) -> None:
    structural_arms = sum(len(pair["arms"]) for pair in old_structural["pairs"])
    text = f"""# V10A superseded execution-harness audit

Status: `FROZEN_BUT_NOT_EXECUTED_SUPERSEDED_V10A`

This audit supersedes the selected experiments, not the accepted V9/V9.1 system or public-profile design. No selected V10A source site, semantic case, structural arm, or private workload was executed while preparing V10A.1.

| Item | Audit conclusion |
|---|---|
| profile freeze | accepted |
| seed construction | accepted |
| prior-case exclusion | accepted |
| selected cases | never executed |
| structural/size projection | accepted |
| semantic execution harness | incomplete: it compared caller-created dictionaries and did not create them through native and canonical execution |

Permanent exclusions added: {len(old_semantic['cases'])} V10A semantic cases/source sites and {structural_arms} V10A structural arms. The full machine-readable exclusion set is `V10_1_SEMANTIC_EXCLUSION_SET.json`; structural sequence signatures are included there as a separate namespace.

Frozen input hashes:

- `{OLD_SEMANTIC.name}`: `{sha(OLD_SEMANTIC)}`
- `{OLD_STRUCTURAL.name}`: `{sha(OLD_STRUCTURAL)}`

These files were read only. Their runtime outcomes remain unknown and must not be obtained later.
"""
    (ROOT / "V10A_SUPERSEDED_EXECUTION_HARNESS_AUDIT.md").write_text(text, encoding="utf-8")


def run_regression() -> dict[str, Any]:
    base_temp = ROOT / "results_v10_1" / "executor_pytest_tmp"
    if base_temp.exists():
        shutil.rmtree(base_temp)
    command = [sys.executable, "-m", "pytest", "tests/test_v10_1_executor.py", "-q", "--basetemp", str(base_temp)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    result = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "canonical_runner": str(GO_RUNNER.relative_to(ROOT)),
        "canonical_runner_available": GO_RUNNER.is_file(),
        "old_v10a_cases_executed": False,
    }
    status = "PASS" if completed.returncode == 0 else "FAIL"
    text = f"""# V10.1 executor regression

Status: **{status}**

- Old V10A selected cases executed: **NO**
- Fixtures: synthetic non-holdout and reconstructed V9.1 development strata only
- Accepted canonical runner available: **{'YES' if GO_RUNNER.is_file() else 'NO'}**
- Exit code: `{completed.returncode}`

## Captured test output

```text
{completed.stdout}{completed.stderr}
```

Handoff and Agent-as-Tool are explicitly ineligible in the frozen adapter registry because V10.1 has no generic canonical bridge for those families. No per-case adapter was added.
"""
    (ROOT / "V10_1_EXECUTOR_REGRESSION.md").write_text(text, encoding="utf-8")
    return result


def freeze_harness(regression: dict[str, Any]) -> dict[str, Any]:
    if regression["returncode"] != 0:
        raise RuntimeError("executor regression failed; harness freeze and reselection are forbidden")
    source_paths = [
        *sorted((ROOT / "v10_1_executor").glob("*.py")),
        *sorted((ROOT / "common_action_gateway_v2" / "canonicalv9").glob("*.go")),
        *sorted((ROOT / "common_action_gateway_v2" / "cmd" / "canonical-v9-runner").glob("*.go")),
        *sorted((ROOT / "common_action_gateway_v2" / "v9ohttp").glob("*.go")),
        ROOT / "v10_holdout" / "harness.py",
        ROOT / "canonical_v9_1" / "projection.py",
        ROOT / "canonical_v9_1" / "runner.py",
        ROOT / "canonical_v9" / "runner.py",
        ROOT / "tests" / "test_v10_1_executor.py",
        ROOT / "scripts" / "prepare_v10_1_refreeze.py",
        GO_RUNNER,
    ]
    hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha(path) for path in source_paths}
    payload: dict[str, Any] = {
        "schema": "AgentTool.V10_1.ExecutionHarnessFreeze/1",
        "status": "FROZEN_AFTER_NON_HOLDOUT_REGRESSION_PASS",
        "old_v10a_selected_cases_executed": False,
        "new_selected_cases_executed": False,
        "semantic_executor": "v10_1_executor.semantic",
        "openai_adapter": "v10_1_executor.frameworks._run_openai",
        "microsoft_adapter": "v10_1_executor.frameworks._run_microsoft",
        "adapter_registry": registry_json(),
        "canonical_semantic_bridge": "v10_1_executor.canonical_bridge.CanonicalSemanticBridge",
        "structural_executor": "v10_1_executor.structural.run_structural_arm",
        "comparison_rules": "SemanticExecutionRecord.projection exact dictionary equality",
        "projection_source": "canonical_v9_1/projection.py",
        "public_profile": "V10-STRICT-H50-C1 unchanged",
        "source_hashes": hashes,
        "test_command": regression["command"],
        "test_output_sha256": sha_bytes((regression["stdout"] + regression["stderr"]).encode()),
    }
    payload["aggregate_sha256"] = sha_bytes(canonical_json(payload))
    write_json(ROOT / "V10_1_EXECUTION_HARNESS_FREEZE.json", payload)
    return payload


def seeds(harness: dict[str, Any]) -> dict[str, Any]:
    v9 = json.loads(V9_FREEZE.read_text(encoding="utf-8"))
    v9_aggregate = v9.get("aggregate_sha256") or sha(V9_FREEZE)
    base = f"{v9_aggregate}|{harness['aggregate_sha256']}"
    result = {
        "schema": "AgentTool.V10_1.SelectionSeeds/1",
        "seed_search": False,
        "v9_functional_freeze_aggregate": v9_aggregate,
        "execution_harness_freeze_aggregate": harness["aggregate_sha256"],
        "semantic_label": "AgentTool-V10.1-semantic-v1",
        "structural_label": "AgentTool-V10.1-structural-v1",
        "semantic_seed": sha_bytes((base + "|AgentTool-V10.1-semantic-v1").encode()),
        "structural_seed": sha_bytes((base + "|AgentTool-V10.1-structural-v1").encode()),
        "order_seed": sha_bytes((base + "|AgentTool-V10.1-order-v1").encode()),
        "derivation": "SHA256(v9 aggregate || harness aggregate || fixed label)",
    }
    write_json(ROOT / "V10_1_SELECTION_SEEDS.json", result)
    return result


def source_file(framework: str, relative: str) -> Path:
    base = ROOT / ("external_stage10/openai-agents-python" if framework == "OpenAI Agents SDK" else "external_stage9/agent-framework")
    return base / relative


def scalar_tool_compatibility(framework: str, path: Path, detail: str) -> tuple[bool, str, str]:
    """Mechanically prove the exact generic adapter's narrow source contract."""

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", detail):
        return False, "DETAIL_IS_NOT_A_CALLABLE_IDENTIFIER", ""
    try:
        source_text = path.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
    except (OSError, SyntaxError, UnicodeError):
        return False, "SOURCE_NOT_LOCALLY_PARSEABLE", ""
    lower_path = str(path).lower()
    if any(token in lower_path for token in ("human_in_the_loop", "hitl", "approval")):
        return False, "APPROVAL_OR_HITL_SEMANTICS_OUTSIDE_GENERIC_ADAPTER", ""
    framework_module = "agents" if framework == "OpenAI Agents SDK" else "agent_framework"
    allowed_symbols = {"tool", "function_tool"} if framework == "OpenAI Agents SDK" else {"tool"}
    imported_decorators: set[str] = set()
    for top_level in tree.body:
        if isinstance(top_level, ast.ImportFrom) and top_level.module and (
            top_level.module == framework_module or top_level.module.startswith(framework_module + ".")
        ):
            imported_decorators.update(
                alias.asname or alias.name for alias in top_level.names if alias.name in allowed_symbols
            )
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != detail:
            continue
        decorators: set[str] = set()
        secret_dependent_decorator_option = False
        for decorator in node.decorator_list:
            value = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(value, ast.Name):
                decorators.add(value.id)
            # Attribute decorators such as ``mcp.tool`` are intentionally not
            # accepted as native framework actions by this generic registry.
            if isinstance(decorator, ast.Call):
                for keyword in decorator.keywords:
                    if keyword.arg in {"approval_mode", "needs_approval", "is_enabled"}:
                        allowed = (
                            isinstance(keyword.value, ast.Constant)
                            and keyword.value.value in {False, "never_require"}
                        )
                        secret_dependent_decorator_option = secret_dependent_decorator_option or not allowed
        positional = list(node.args.posonlyargs) + list(node.args.args)
        if len(positional) != 1 or node.args.vararg or node.args.kwarg or node.args.kwonlyargs:
            continue
        annotation = positional[0].annotation
        if not isinstance(annotation, ast.Name) or annotation.id != "str":
            continue
        if not (decorators & imported_decorators):
            continue
        if secret_dependent_decorator_option:
            return False, "APPROVAL_OR_DYNAMIC_ENABLEMENT_NOT_PRESERVED", ""
        return True, "FROZEN_GENERIC_SCALAR_TOOL_ADAPTER", positional[0].arg
    return False, "NO_ONE_STRING_ARGUMENT_DECORATED_TOOL_DEFINITION", ""


def build_pool(excluded_keys: set[str], semantic_seed: str) -> list[dict[str, Any]]:
    with CORPUS.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    values: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        adapter = eligible_adapter(row["framework"], row["action_site_kind"])
        source_key = site_key(row["framework"], row["relative_path"], row["line"])
        file_key = f"{row['framework']}|{row['relative_path']}|*"
        prior = source_key in excluded_keys or file_key in excluded_keys
        path = source_file(row["framework"], row["relative_path"])
        source_compatible, compatibility_reason, argument_name = (
            scalar_tool_compatibility(row["framework"], path, row["detail"])
            if adapter is not None and row["v6_disposition"] == "MEDIATED" and path.is_file()
            else (False, "NO_FROZEN_ADAPTER_OR_SOURCE", "")
        )
        compatible = adapter is not None and source_compatible
        if source_key in seen:
            continue
        seen.add(source_key)
        score = sha_bytes(f"{semantic_seed}|{source_key}".encode())
        values.append({
            "framework": row["framework"],
            "source_path": row["relative_path"],
            "source_sha": sha(path) if path.is_file() else "MISSING",
            "source_line": int(row["line"]),
            "action_family": row["action_site_kind"],
            "adapter_id": adapter.adapter_id if adapter else "NONE",
            "native_executor_verified": str(bool(compatible)).lower(),
            "canonical_executor_verified": str(bool(compatible)).lower(),
            "external_network_required": "false" if compatible else "unknown",
            "prior_exclusion_status": "EXCLUDED" if prior else "CLEAR",
            "deterministic_selection_score": score,
            "eligible": str(bool(compatible and not prior)).lower(),
            "detail": row["detail"],
            "argument_name": argument_name,
            "source_compatibility_result": compatibility_reason,
            "compatibility_scope": adapter.source_compatibility_rule if adapter else "NO_FROZEN_ADAPTER",
        })
    fields = list(values[0])
    write_csv(ROOT / "V10_1_SEMANTIC_ELIGIBLE_POOL.csv", values, fields)
    return values


def select_semantic(pool: list[dict[str, Any]], seeds_value: dict[str, Any]) -> list[dict[str, Any]]:
    eligible = [row for row in pool if row["eligible"] == "true"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        grouped[row["framework"]].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: row["deterministic_selection_score"])
    selected: list[dict[str, Any]] = []
    frameworks = ["OpenAI Agents SDK", "Microsoft Agent Framework"]
    for index in range(16):
        for framework in frameworks:
            if index < len(grouped[framework]):
                selected.append(grouped[framework][index])
    cases: list[dict[str, Any]] = []
    for index, row in enumerate(selected, 1):
        cases.append({
            "case_id": f"V10_1S-{index:03d}",
            "selection_rank": index,
            "framework": row["framework"],
            "pinned_commit": next(item["pinned_commit"] for item in csv.DictReader(CORPUS.open(encoding="utf-8-sig")) if item["framework"] == row["framework"]),
            "source": {"path": row["source_path"], "sha256": row["source_sha"], "line": int(row["source_line"]), "detail": row["detail"]},
            "action_family": "tool",
            "adapter_id": row["adapter_id"],
            "logical_action_name": row["detail"],
            "argument_name": row["argument_name"],
            "deterministic_scenario": "READ_ONLY_SUCCESS",
            "deterministic_test_input": {"prompt": f"local-v10-1-input-{index:03d}", "protected_argument": f"argument-v10-1-{index:03d}"},
            "local_provider_configuration": {"provider": "LOCAL_DETERMINISTIC_PROVIDER_V10_1", "outcome": "SUCCESS", "external_network_required": False},
            "declared_effect_semantics": "READ_ONLY",
            "public_profile_id": "V10-STRICT-H50-C1",
            "operation_ids": [f"v101s{index:04d}"],
            "selected_case_executed": False,
        })
    counts = Counter(case["framework"] for case in cases)
    manifest = {
        "schema": "AgentTool.V10_1.CanonicalSemanticHoldoutFreeze/1",
        "phase": "V10A.1_FREEZE_ONLY",
        "selected_holdout_executed": False,
        "selection_seed": seeds_value["semantic_seed"],
        "selection_rule": "balanced deterministic score order over executor-verified, local, nonexcluded generic Tool sites; maximum 16 per framework",
        "target_cases": 32,
        "selected_cases": len(cases),
        "framework_counts": dict(counts),
        "documented_shortages": {framework: max(0, 16 - counts[framework]) for framework in ["OpenAI Agents SDK", "Microsoft Agent Framework"]},
        "cases": cases,
    }
    write_json(ROOT / "CANONICAL_SEMANTIC_HOLDOUT_V10_1_FREEZE.json", manifest)
    flat = [{"case_id": c["case_id"], "framework": c["framework"], "source_path": c["source"]["path"], "source_sha": c["source"]["sha256"], "source_line": c["source"]["line"], "action_family": c["action_family"], "adapter_id": c["adapter_id"], "logical_action_name": c["logical_action_name"], "argument_name": c["argument_name"], "operation_id": c["operation_ids"][0], "selected_case_executed": False} for c in cases]
    write_csv(ROOT / "CANONICAL_SEMANTIC_HOLDOUT_V10_1_CASES.csv", flat, list(flat[0]) if flat else ["case_id"])
    return cases


def private_action(index: int, capability: str, argument: str) -> dict[str, Any]:
    kind = "AGENT_SERVICE" if capability.startswith("agent.service") else ("EXTERNAL_HTTP" if capability == "external.local" else "TOOL")
    semantics = "NON_IDEMPOTENT_EFFECT" if capability in {"tool.nonidem", "agent.service.13"} else ("IDEMPOTENT_EFFECT" if capability in {"tool.idem", "agent.service.12"} else "READ_ONLY")
    return {"operation_id": f"v101p{index:06d}", "action_kind": kind, "capability": capability, "effect_semantics": semantics, "protected_argument": argument}


def structural_pairs(seed: str, old_signatures: set[str]) -> list[dict[str, Any]]:
    counter = 1

    def pick(label: str, options: list[int]) -> int:
        return options[int(sha_bytes(f"{seed}|{label}".encode())[:8], 16) % len(options)]

    def actions(capabilities: list[str], label: str) -> list[dict[str, Any]]:
        nonlocal counter
        result = []
        for position, capability in enumerate(capabilities):
            result.append(private_action(counter, capability, f"v101-{label}-{position}"))
            counter += 1
        return result

    equal_a = pick("equal-a", [9, 11, 13])
    equal_b = pick("equal-b", [10, 12, 14])
    repetition_count = pick("repetition", [16, 18, 20])
    frequency_count = pick("frequency", [18, 20, 22])
    rare_count = pick("rare", [18, 20, 24])
    rare_position = pick("rare-position", list(range(rare_count)))
    rare_sequence = ["tool.read"] * rare_count
    rare_sequence[rare_position] = "tool.idem"
    definitions = [
        ("AGENT_IDENTITY", 1, "agent.a", ["tool.a"] * equal_a, 2, "agent.b", ["tool.b"] * equal_a),
        ("TARGET_DESTINATION", 10, "agent.tools", ["tool.read"] * equal_b, 10, "agent.tools", ["external.local"] * equal_b),
        ("ACTION_KIND", 10, "agent.tools", ["tool.read"] * equal_a, 11, "agent.service.11", ["agent.service.11"] * equal_a),
        ("PRIVATE_ACTION_COUNT", 10, "agent.tools", ["tool.read"] * pick("count-low", [3, 4, 5]), 10, "agent.tools", ["tool.read"] * pick("count-high", [19, 21, 23])),
        ("REPETITION", 10, "agent.tools", ["tool.read"] * repetition_count, 10, "agent.tools", (["tool.read", "tool.idem"] * (repetition_count // 2))),
        ("FREQUENCY_SKEW", 10, "agent.tools", ["tool.read"] * (frequency_count - 1) + ["tool.idem"], 10, "agent.tools", ["tool.read"] * (frequency_count // 2) + ["tool.idem"] * (frequency_count // 2)),
        ("RARE_TARGET", 10, "agent.tools", rare_sequence, 10, "agent.tools", ["tool.read"] * rare_count),
        ("TRANSITION_PATTERN", 10, "agent.tools", ["tool.read", "tool.idem"] * pick("transition", [8, 9, 10]), 10, "agent.tools", ["tool.read", "tool.nonidem"] * pick("transition", [8, 9, 10])),
        ("PRIVATE_ARGUMENT_LENGTH", 10, "agent.tools", ["tool.read"] * pick("argument-length", [7, 8, 9]), 10, "agent.tools", ["tool.read"] * pick("argument-length", [7, 8, 9])),
        ("COMPLETION_BEHAVIOR", 10, "agent.tools", ["tool.read"] * equal_b, 13, "agent.service.13", ["agent.service.13"] * equal_b),
    ]
    pairs: list[dict[str, Any]] = []
    for index, definition in enumerate(definitions, 1):
        stratum, aid, acap, caps_a, bid, bcap, caps_b = definition
        args_a = "x" if stratum != "PRIVATE_ARGUMENT_LENGTH" else "a"
        args_b = "y" if stratum != "PRIVATE_ARGUMENT_LENGTH" else "b" * 700
        arms = [
            {"arm_id": f"V10_1P{index}-A", "public_profile_id": "V10-STRICT-H50-C1", "private_agent_id": aid, "private_agent_capability": acap, "private_actions": actions(caps_a, f"{seed[:8]}-{index}a-{args_a}")},
            {"arm_id": f"V10_1P{index}-B", "public_profile_id": "V10-STRICT-H50-C1", "private_agent_id": bid, "private_agent_capability": bcap, "private_actions": actions(caps_b, f"{seed[:8]}-{index}b-{args_b}")},
        ]
        # The new arguments and operation IDs are seed-versioned, but still
        # verify exact exclusion against every old private sequence.
        for arm in arms:
            signature = structural_sequence_signature_from_parts(
                int(arm["private_agent_id"]), str(arm["private_agent_capability"]), list(arm["private_actions"])
            )
            if signature in old_signatures:
                raise AssertionError("new structural arm duplicates a V10A private sequence")
            arm["private_sequence_sha256"] = signature
            arm["selected_arm_executed"] = False
        pairs.append({"pair_id": f"V10_1P{index}", "stratum": stratum, "selection_method": "single deterministic construction from structural seed", "structural_seed": seed, "arms": arms})
    return pairs


def write_structural(pairs: list[dict[str, Any]]) -> None:
    manifest = {"schema": "AgentTool.V10_1.StructuralSizeHoldoutFreeze/1", "phase": "V10A.1_FREEZE_ONLY", "selected_holdout_executed": False, "public_profile_id": "V10-STRICT-H50-C1", "internal_external_stratum": "NOT_APPLICABLE", "pairs": pairs}
    write_json(ROOT / "STRUCTURAL_SIZE_HOLDOUT_V10_1_FREEZE.json", manifest)
    rows = []
    for pair in pairs:
        for arm in pair["arms"]:
            rows.append({"pair_id": pair["pair_id"], "stratum": pair["stratum"], "arm_id": arm["arm_id"], "agent_id": arm["private_agent_id"], "agent_capability": arm["private_agent_capability"], "actual_real_actions": len(arm["private_actions"]), "private_sequence_sha256": arm["private_sequence_sha256"], "selected_arm_executed": False})
    write_csv(ROOT / "STRUCTURAL_SIZE_HOLDOUT_V10_1_PAIRS.csv", rows, list(rows[0]))


def write_order(cases: list[dict[str, Any]], pairs: list[dict[str, Any]], order_seed: str) -> None:
    semantic = sorted([case["case_id"] for case in cases], key=lambda value: sha_bytes(f"{order_seed}|semantic|{value}".encode()))
    arms = [arm["arm_id"] for pair in pairs for arm in pair["arms"]]
    structural = sorted(arms, key=lambda value: sha_bytes(f"{order_seed}|structural|{value}".encode()))
    write_json(ROOT / "V10_1_EXECUTION_ORDER.json", {"schema": "AgentTool.V10_1.ExecutionOrder/1", "phase": "FROZEN_NOT_EXECUTED", "order_seed": order_seed, "semantic_case_order": semantic, "structural_arm_order": structural, "selected_cases_executed": False})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    old_semantic, old_structural = assert_old_manifests_untouched()
    excluded_keys, exclusions = historical_semantic_sites(old_semantic)
    old_structural_signatures: set[str] = set()
    for pair in old_structural["pairs"]:
        for arm in pair["arms"]:
            signature = structural_sequence_signature(arm)
            old_structural_signatures.add(signature)
            exclusions.append({"kind": "V10A_STRUCTURAL_PRIVATE_SEQUENCE", "key": signature, "arm_id": arm["arm_id"], "reason": "FROZEN_BUT_NOT_EXECUTED_SUPERSEDED_V10A"})
    write_json(ROOT / "V10_1_SEMANTIC_EXCLUSION_SET.json", {"schema": "AgentTool.V10_1.ExclusionSet/1", "old_v10a_status": "FROZEN_BUT_NOT_EXECUTED_SUPERSEDED_V10A", "entries": exclusions})
    create_supersession_audit(old_semantic, old_structural, exclusions)
    if args.audit_only:
        return
    regression = run_regression()
    if regression["returncode"] != 0:
        print(json.dumps({"status": "BLOCKED_BEFORE_HARNESS_FREEZE", "regression": regression}, indent=2))
        raise SystemExit(2)
    harness = freeze_harness(regression)
    seeds_value = seeds(harness)
    pool = build_pool(excluded_keys, seeds_value["semantic_seed"])
    cases = select_semantic(pool, seeds_value)
    pairs = structural_pairs(seeds_value["structural_seed"], old_structural_signatures)
    write_structural(pairs)
    write_order(cases, pairs, seeds_value["order_seed"])
    audit = f"""# V10A.1 freeze audit

Status: **PASS**

- Old V10A selected cases executed: **NO**
- Execution harness frozen before reselection: **PASS**
- New seed search: **NO**
- New semantic executable pool: **{sum(row['eligible'] == 'true' for row in pool)}** of {len(pool)} unique corpus sites
- New semantic cases frozen: **{len(cases)}**
- New structural pairs frozen: **{len(pairs)}**
- New selected cases executed: **NO**
- V10 public-profile security change: **NONE**
- Timing privacy: **OPEN / NOT TESTED**
- Packet-level timing: **OPEN**
- Hardware TEE: **NOT_TESTED**

The adapter registry is intentionally narrow: only generic scalar Tool semantics are executable. Handoff, Agent-as-Tool, hosted Tools, MCP, streaming and source-specific schemas remain ineligible rather than being projected into success.
"""
    (ROOT / "V10A_1_FREEZE_AUDIT.md").write_text(audit, encoding="utf-8")
    assert_old_manifests_untouched()
    print(json.dumps({"status": "PASS", "eligible": sum(row["eligible"] == "true" for row in pool), "semantic_cases": len(cases), "structural_pairs": len(pairs), "old_executed": False, "new_executed": False}, indent=2))


if __name__ == "__main__":
    main()

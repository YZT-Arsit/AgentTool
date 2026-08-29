from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptographic_closure.pir_backend import SIMPLEPIR_COMMIT
from v11a_confirmatory.orchestrator import (
    PROFILE_ID,
    load_semantic_case,
    load_structural_arm,
    load_trajectory_case,
)


BASE_COMMIT = "f6860baaab8927f9b0b66153959b55d8ca072c23"
V11_4_EXECUTION_FREEZE = ROOT / "V11_4_ONLINE_EXECUTION_HARNESS_FREEZE.json"
V11_4_1_BASELINE_FREEZE = ROOT / "V11_4_1_CONFIRMATORY_BASELINE_FREEZE.json"
PROFILE = ROOT / "PUBLIC_PROFILE_ONLINE_V11_4.json"
CORPUS = ROOT / "ACTION_MEDIATION_CORPUS_V6.csv"
ABORTED_AUDIT = ROOT / "V11A_PRE_SELECTION_SYSTEM_AUDIT.json"
RESTART_AUDIT = ROOT / "V11A_RESTART_PRE_SELECTION_SYSTEM_AUDIT.json"
ENVIRONMENT_FREEZE = ROOT / "V11A_EXECUTION_ENVIRONMENT_FREEZE.json"
ORCHESTRATOR_FREEZE = ROOT / "V11A_CONFIRMATORY_ORCHESTRATOR_FREEZE.json"
EXCLUSION_SET = ROOT / "V11A_MASTER_EXCLUSION_SET.json"
UNIVERSE_FREEZE = ROOT / "V11A_CANDIDATE_UNIVERSES_FREEZE.json"
SEEDS = ROOT / "V11A_SELECTION_SEEDS.json"

OPENAI_ROOT = ROOT / "external_stage10" / "openai-agents-python"
MICROSOFT_ROOT = ROOT / "external_stage9" / "agent-framework"
FRAMEWORK_ROOTS = {
    "OpenAI Agents SDK": OPENAI_ROOT,
    "Microsoft Agent Framework": MICROSOFT_ROOT,
}
FRAMEWORK_COMMITS = {
    "OpenAI Agents SDK": "a40ae9803e6b7a79faa246293f56adb100d5868b",
    "Microsoft Agent Framework": "af461de51da16f5cb800ff7febc0f8f96355607a",
}
LABELS = {
    "s1": "AgentTool-V11A-source-semantic-v1",
    "s2": "AgentTool-V11A-composition-semantic-v1",
    "s3": "AgentTool-V11A-trajectory-semantic-v1",
    "s4": "AgentTool-V11A-effect-contract-v1",
    "structural": "AgentTool-V11A-structural-v1",
    "order": "AgentTool-V11A-execution-order-v1",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen V11A artifact: {path.name}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen V11A artifact: {path.name}")
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, value: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen V11A artifact: {path.name}")
    path.write_text(value, encoding="utf-8")


def git_bytes(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def protected_paths() -> list[Path]:
    paths: list[Path] = []
    for directory in (
        "action_privacy_v8",
        "canonical_v9",
        "canonical_v9_1",
        "v11_full_scope",
        "v11_online",
        "v11_4",
        "common_action_gateway_v2/canonicalv9",
        "common_action_gateway_v2/v9ohttp",
    ):
        paths.extend(path for path in (ROOT / directory).rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    paths.extend(
        ROOT / name
        for name in (
            "cryptographic_closure/pir_backend.py",
            "PUBLIC_PROFILE_ONLINE_V11_4.json",
            "V11_4_ONLINE_EXECUTION_HARNESS_FREEZE.json",
            "scripts/freeze_v11_4_profile_candidates.py",
            "scripts/run_v11_4_profile_qualification.py",
            "scripts/run_v11_4_post_gate_repairs.py",
        )
    )
    return sorted(set(paths))


def freeze_preselection_audit() -> dict[str, Any]:
    head = git_head()
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_COMMIT, head],
        cwd=ROOT,
        capture_output=True,
    )
    if ancestry.returncode != 0:
        raise RuntimeError("the exact accepted V11.4 base commit is not an ancestor of the restart checkout")
    baseline = json.loads(V11_4_1_BASELINE_FREEZE.read_text(encoding="utf-8"))
    if baseline.get("v11a_restart_allowed") != "YES" or baseline.get("stronger_structural_recompute") != {"passed": 12, "total": 12}:
        raise RuntimeError("V11.4.1 analysis baseline is not aligned")
    aborted = json.loads(ABORTED_AUDIT.read_text(encoding="utf-8"))
    if aborted.get("terminal_classification") != "ABORTED_BEFORE_SELECTION_PROJECTION_BASELINE_MISMATCH":
        raise RuntimeError("failed V11A pre-selection audit was not preserved")
    rows = []
    for path in protected_paths():
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        base_hash = sha256_bytes(git_bytes(BASE_COMMIT, relative))
        actual_hash = sha256(path)
        rows.append({"path": relative, "base_commit_sha256": base_hash, "actual_sha256": actual_hash, "match": base_hash == actual_hash})
    all_match = all(item["match"] for item in rows)
    value = {
        "schema": "AgentTool.V11A.RestartPreSelectionSystemAudit/1",
        "v11_4_base_commit": BASE_COMMIT,
        "head_commit_at_v11a_restart": head,
        "v11_4_base_commit_is_ancestor": True,
        "v11_4_freeze_manifest_sha256": sha256(V11_4_EXECUTION_FREEZE),
        "v11_4_1_analysis_baseline_freeze_sha256": sha256(V11_4_1_BASELINE_FREEZE),
        "aborted_preselection_audit_sha256": sha256(ABORTED_AUDIT),
        "aborted_preselection_audit_preserved": True,
        "protected_path_count": len(rows),
        "protected_paths_all_match_base_commit": all_match,
        "protected_path_hashes": rows,
        "v11a_freeze_invalidated": not all_match,
        "holdout_selection_allowed": all_match,
        "selected_holdout_cases_executed": 0,
    }
    write_json(RESTART_AUDIT, value)
    if not all_match:
        raise RuntimeError("V11A_FREEZE_INVALIDATED=YES")
    return value


def freeze_environment() -> dict[str, Any]:
    host = json.loads((ROOT / "results_v11_4_development" / "qualification_host.json").read_text(encoding="utf-8"))
    ohttp = json.loads((ROOT / "OHTTP_VENDOR_PROVENANCE_V9.json").read_text(encoding="utf-8"))
    simplepir_root = ROOT / "external_pir" / "simplepir"
    simplepir_head = subprocess.check_output(
        ["git", "-C", str(simplepir_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if simplepir_head != SIMPLEPIR_COMMIT:
        raise RuntimeError("local SimplePIR source does not match the frozen revision")
    value = {
        "schema": "AgentTool.V11A.ExecutionEnvironmentFreeze/1",
        "v11_4_base_commit": BASE_COMMIT,
        "linux_os_platform": host["platform"],
        "linux_kernel": host["kernel"],
        "linux_cpu": host["cpu"],
        "python_version": host["python"],
        "go_version": host["go"],
        "openai_agents_sdk_revision": FRAMEWORK_COMMITS["OpenAI Agents SDK"],
        "microsoft_agent_framework_revision": FRAMEWORK_COMMITS["Microsoft Agent Framework"],
        "simplepir_revision": SIMPLEPIR_COMMIT,
        "simplepir_revision_verified_from_local_git": simplepir_head,
        "simplepir_bridge_source_sha256": sha256(ROOT / "pir_integration" / "simplepir_bridge" / "main.go"),
        "simplepir_bridge_binary_sha256": "NOT_PRESENT_ON_WINDOWS; canonical V11.4 Linux runner hash is frozen separately",
        "ohttp_go_expected_revision": ohttp["expected_upstream_commit"],
        "ohttp_go_provenance_class": ohttp["provenance_class"],
        "ohttp_go_source_tree_sha256": ohttp["source_tree_sha256"],
        "canonical_linux_binary_sha256": host["runner_sha256"],
        "timing_privacy": "OPEN / NOT TESTED",
        "packet_level_timing": "OPEN",
        "hardware_tee": "NOT_TESTED",
        "selected_holdout_cases_executed": 0,
    }
    write_json(ENVIRONMENT_FREEZE, value)
    return value


def freeze_orchestrator() -> dict[str, Any]:
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_v11a_confirmatory.py", "-v"]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    source_paths = [
        ROOT / "v11a_confirmatory" / "__init__.py",
        ROOT / "v11a_confirmatory" / "orchestrator.py",
        ROOT / "v11a_confirmatory" / "projection.py",
        ROOT / "tests" / "test_v11a_confirmatory.py",
        ROOT / "scripts" / "freeze_v11a_confirmatory.py",
    ]
    value = {
        "schema": "AgentTool.V11A.ConfirmatoryOrchestratorFreeze/1",
        "status": "FROZEN_BEFORE_CANDIDATE_UNIVERSE_CONSTRUCTION",
        "source_hashes": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in source_paths},
        "test_command": command,
        "test_output_sha256": sha256_bytes((completed.stdout + completed.stderr).encode()),
        "test_result": "4/4 PASS",
        "execution_guard": "V11A development fixtures require DEV- prefix; selected cases require explicit V11B permit",
        "case_id_specific_branches": False,
        "automatic_retries": False,
        "selected_holdout_cases_executed": 0,
    }
    value["aggregate_sha256"] = canonical_sha(value)
    write_json(ORCHESTRATOR_FREEZE, value)
    return value


def normalize_source_path(value: str) -> str:
    path = value.replace("\\", "/")
    for prefix in ("external_stage10/openai-agents-python/", "external_stage9/agent-framework/"):
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def source_key(framework: str, path: str, line: int | str) -> str:
    return f"{framework}|{normalize_source_path(path)}|{line}"


def workload_signature(value: Any) -> str:
    return canonical_sha(value)


def historical_arm_signature(arm: dict[str, Any]) -> str:
    """Canonical private-workload signature with operation randomness removed."""

    actions = []
    for item in arm.get("private_actions", []):
        actions.append({key: value for key, value in item.items() if key != "operation_id"})
    return workload_signature(
        {
            "private_agent_id": arm.get("private_agent_id"),
            "private_agent_capability": arm.get("private_agent_capability"),
            "actual_real_action_count": arm.get("actual_real_action_count", len(actions)),
            "private_actions": actions,
        }
    )


def master_exclusions() -> dict[str, Any]:
    exact: dict[str, set[str]] = defaultdict(set)
    files: dict[str, set[str]] = defaultdict(set)
    reasons: list[dict[str, str]] = []

    def exclude(framework: str, path: str, line: str | int | None, reason: str) -> None:
        if not framework or not path:
            return
        normalized = normalize_source_path(path)
        if line is None or str(line).strip() in {"", "0", "*"}:
            key = source_key(framework, normalized, "*")
            if key not in files[framework]:
                files[framework].add(key)
                reasons.append({"kind": "SOURCE_FILE", "key": key, "reason": reason})
        else:
            key = source_key(framework, normalized, int(float(str(line))))
            if key not in exact[framework]:
                exact[framework].add(key)
                reasons.append({"kind": "SOURCE_SITE", "key": key, "reason": reason})

    historical_csvs = set(ROOT.glob("ACTION_SEMANTIC_HOLDOUT_V*.csv"))
    historical_csvs.update(ROOT.glob("*SEMANTIC*RESULTS*.csv"))
    historical_csvs.update(
        path
        for path in (
            ROOT / "CANONICAL_SEMANTIC_HOLDOUT_V10_CASES.csv",
            ROOT / "CANONICAL_SEMANTIC_HOLDOUT_V10_1_CASES.csv",
            ROOT / "V10_1_SEMANTIC_ELIGIBLE_POOL.csv",
        )
        if path.is_file()
    )
    for path in sorted(historical_csvs):
        try:
            rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        except UnicodeError:
            continue
        for row in rows:
            framework = row.get("framework", "")
            source = row.get("source_path") or row.get("path") or ""
            line = row.get("source_line") or row.get("line")
            # An eligible-pool row was observed only when selected or already
            # excluded; do not exclude every merely enumerated candidate.
            if path.name == "V10_1_SEMANTIC_ELIGIBLE_POOL.csv" and row.get("prior_exclusion_status") != "EXCLUDED":
                continue
            exclude(framework, source, line, path.name)

    future = json.loads((ROOT / "V11_FUTURE_EXCLUSION_SET.json").read_text(encoding="utf-8"))
    for item in future["semantic_source_sites"]:
        framework = "OpenAI Agents SDK" if (OPENAI_ROOT / item["path"]).is_file() else "Microsoft Agent Framework"
        exclude(framework, item["path"], item.get("line"), "V11_FUTURE_EXCLUSION_SET.json")

    workload_entries: list[dict[str, Any]] = []
    for item in future["structural_private_sequences"]:
        for arm in item["arms"]:
            workload_entries.append(
                {
                    "signature": historical_arm_signature(arm),
                    "origin": item["origin"],
                    "kind": "FROZEN_STRUCTURAL_SEQUENCE",
                }
            )
    # V11/V11.4 development families are excluded conservatively by normalized
    # family contract in addition to exact older sequence signatures.
    development_families = [
        "V11_TOOL_SCHEMA_MATRIX",
        "V11_EFFECT_OUTCOME_MATRIX",
        "V11_OPENAI_AGENT_AS_TOOL",
        "V11_OPENAI_HANDOFF",
        "V11_MICROSOFT_AGENT_AS_TOOL",
        "V11_DYNAMIC_CAUSAL_SEQUENCE_1_2_3_5_10_20_30_50",
        "V11_TOOL_TO_TOOL",
        "V11_TOOL_TO_AGENT_AS_TOOL",
        "V11_AGENT_AS_TOOL_TO_TOOL",
        "V11_TOOL_TO_HANDOFF",
        "V11_INTERNAL_TO_EXTERNAL",
        "V11_EXTERNAL_TO_INTERNAL",
        "V11_STRUCTURED_TOOL_TO_AGENT_AS_TOOL",
        "V11_STRUCTURAL_AGENT_IDENTITY",
        "V11_STRUCTURAL_TOOL_ROUTE",
        "V11_STRUCTURAL_ACTION_KIND",
        "V11_STRUCTURAL_ACTION_COUNT",
        "V11_STRUCTURAL_REPETITION_FREQUENCY_RARE_TRANSITION",
        "V11_STRUCTURAL_ARGUMENT_LENGTH_READINESS_INTERNAL_EXTERNAL_CAUSAL_DEPTH",
    ]
    workload_entries.extend(
        {"signature": workload_signature({"development_family": item}), "origin": "V11-V11.4 development", "kind": "FAMILY_CONTRACT"}
        for item in development_families
    )
    value = {
        "schema": "AgentTool.V11A.MasterExclusionSet/1",
        "historical_scope": "V6 through V11.4 semantic, trajectory, structural, scheduler, profile, and frozen-but-unexecuted cases",
        "source_site_exact": sorted(set().union(*exact.values()) if exact else set()),
        "source_file_wildcards": sorted(set().union(*files.values()) if files else set()),
        "source_exclusion_reasons": reasons,
        "workload_signatures": sorted(workload_entries, key=lambda item: (item["signature"], item["origin"])),
        "counts": {
            "exact_source_sites": sum(len(value) for value in exact.values()),
            "whole_source_files": sum(len(value) for value in files.values()),
            "workload_signatures": len(workload_entries),
        },
        "selected_holdout_cases_executed": 0,
    }
    value["aggregate_sha256"] = canonical_sha(value)
    write_json(EXCLUSION_SET, value)
    return value


def decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        return decorator_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def annotation_type(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name) and node.id in {"str", "int", "bool"}:
        return node.id
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "Optional":
        inner = annotation_type(node.slice)
        return "optional_str" if inner == "str" else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        values = {annotation_type(node.left), annotation_type(node.right)}
        if values == {"str", None} and (
            (isinstance(node.left, ast.Constant) and node.left.value is None)
            or (isinstance(node.right, ast.Constant) and node.right.value is None)
        ):
            return "optional_str"
    return None


def values_for(fields: list[dict[str, str]], token: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for index, field in enumerate(fields):
        kind = field["primitive_type"]
        result[field["name"]] = {
            "str": f"v11a-{token}-{index}",
            "int": 7 + index,
            "bool": index % 2 == 0,
            "optional_str": None,
        }[kind]
    return result


def build_s1_universe(exclusions: dict[str, Any]) -> list[dict[str, Any]]:
    excluded_exact = set(exclusions["source_site_exact"])
    excluded_files = set(exclusions["source_file_wildcards"])
    corpus_rows = list(csv.DictReader(CORPUS.open(encoding="utf-8-sig")))
    rows_by_file: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in corpus_rows:
        if row["v6_disposition"] == "MEDIATED" and row["action_site_kind"] == "tool":
            rows_by_file[(row["framework"], row["relative_path"])].append(row)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for (framework, relative), rows in sorted(rows_by_file.items()):
        path = FRAMEWORK_ROOTS[framework] / relative
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeError):
            continue
        corpus_sites = {(int(row["line"]), row["detail"]): row for row in rows}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorator_lines = [getattr(item, "lineno", node.lineno) for item in node.decorator_list]
            possible_lines = {node.lineno, *decorator_lines}
            matching = [corpus_sites[(line, node.name)] for line in possible_lines if (line, node.name) in corpus_sites]
            if not matching or not any(decorator_name(item) in {"tool", "function_tool"} for item in node.decorator_list):
                continue
            positional = list(node.args.posonlyargs) + list(node.args.args)
            if not 1 <= len(positional) <= 3 or node.args.vararg or node.args.kwarg or node.args.kwonlyargs:
                continue
            fields = []
            for arg in positional:
                kind = annotation_type(arg.annotation)
                if kind is None or not arg.arg.isidentifier():
                    fields = []
                    break
                fields.append({"name": arg.arg, "primitive_type": kind})
            if not fields:
                continue
            optional_seen = False
            schema_order_valid = True
            for field in fields:
                if field["primitive_type"].startswith("optional_"):
                    optional_seen = True
                elif optional_seen:
                    schema_order_valid = False
                    break
            if not schema_order_valid:
                continue
            site_line = int(matching[0]["line"])
            key = source_key(framework, relative, site_line)
            file_key = source_key(framework, relative, "*")
            if key in seen or key in excluded_exact or file_key in excluded_files:
                continue
            seen.add(key)
            candidate_id = "S1U-" + sha256_bytes(key.encode())[:16]
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "framework": framework,
                    "pinned_commit": FRAMEWORK_COMMITS[framework],
                    "source_path": relative,
                    "source_sha256": sha256(path),
                    "source_line": site_line,
                    "source_detail": node.name,
                    "frozen_corpus_disposition": "MEDIATED",
                    "adapter_id": "V11A_GENERIC_BOUNDED_TOOL_ADAPTER",
                    "argument_schema": {"schema_id": "SOURCE_" + "_".join(field["primitive_type"].upper() for field in fields), "fields": fields},
                    "arguments": values_for(fields, candidate_id[-8:]),
                    "effect_semantics": "READ_ONLY",
                    "scenario": "SUCCESS",
                    "effect_contract_origin": "SYNTHETIC_CONFIRMATORY_CONTRACT",
                    "external_network_required": False,
                    "public_profile_id": PROFILE_ID,
                }
            )
    return sorted(candidates, key=lambda item: item["candidate_id"])


def schema_one_str() -> dict[str, Any]:
    return {"schema_id": "ONE_STR", "fields": [{"name": "task", "primitive_type": "str"}]}


def route_for_effect(effect: str) -> tuple[int, str]:
    agent_id = {"READ_ONLY": 11, "IDEMPOTENT_EFFECT": 12, "NON_IDEMPOTENT_EFFECT": 13}[effect]
    return agent_id, f"agent.service.{agent_id}"


def action(
    case_id: str,
    framework: str,
    *,
    family: str = "TOOL",
    subtype: str | None = None,
    capability: str = "tool.read",
    agent_id: int = 10,
    agent_capability: str = "agent.tools",
    effect: str = "READ_ONLY",
    scenario: str = "SUCCESS",
    arguments: dict[str, Any] | None = None,
    schema: dict[str, Any] | None = None,
    placement: str = "EXTERNAL",
    continuation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    schema = schema or {"schema_id": "ONE_STR", "fields": [{"name": "city", "primitive_type": "str"}]}
    arguments = arguments or {schema["fields"][0]["name"]: f"fresh-{case_id}"}
    return {
        "case_id": case_id,
        "framework": framework,
        "action_family": family,
        "agent_service_subtype": subtype,
        "logical_action_name": "v11a_" + re.sub(r"[^A-Za-z0-9_]", "_", case_id).lower(),
        "argument_schema": schema,
        "arguments": arguments,
        "effect_semantics": effect,
        "scenario": scenario,
        "operation_id": ("op" + re.sub(r"[^A-Za-z0-9]", "", case_id))[:32],
        "capability": capability,
        "agent_id": agent_id,
        "agent_capability": agent_capability,
        "placement": placement,
        "continuation": continuation or {},
        "public_profile_id": PROFILE_ID,
    }


def build_s2_universe() -> list[dict[str, Any]]:
    values = []
    families = (
        ("OPENAI_AGENT_AS_TOOL", "OpenAI Agents SDK", "AGENT_AS_TOOL"),
        ("OPENAI_HANDOFF", "OpenAI Agents SDK", "HANDOFF"),
        ("MICROSOFT_AGENT_AS_TOOL", "Microsoft Agent Framework", "AGENT_AS_TOOL"),
    )
    for family, framework, subtype in families:
        for effect in ("READ_ONLY", "IDEMPOTENT_EFFECT", "NON_IDEMPOTENT_EFFECT"):
            agent_id, capability = route_for_effect(effect)
            for scenario in ("SUCCESS", "ERROR", "BOUNDED_TIMEOUT"):
                for variant in (1, 2):
                    candidate_id = f"S2U-{family}-{effect}-{scenario}-V{variant}"
                    item = action(
                        candidate_id,
                        framework,
                        family="AGENT_SERVICE",
                        subtype=subtype,
                        capability=capability,
                        agent_id=agent_id,
                        agent_capability=capability,
                        effect=effect,
                        scenario=scenario,
                        schema=schema_one_str(),
                        arguments={"task": f"fresh-composition-{family.lower()}-{effect.lower()}-{scenario.lower()}-{variant}"},
                    )
                    item.update({"candidate_id": candidate_id, "composition_family": family, "effect_contract_origin": "SYNTHETIC_CONFIRMATORY_CONTRACT"})
                    values.append(item)
    return values


def sequence_actions(candidate_id: str, framework: str, depth: int, alternating: bool = False) -> list[dict[str, Any]]:
    values = []
    for index in range(depth):
        effect = "IDEMPOTENT_EFFECT" if alternating and index % 2 else "READ_ONLY"
        capability = "tool.idem" if effect == "IDEMPOTENT_EFFECT" else "tool.read"
        values.append(
            action(
                f"{candidate_id}-A{index + 1}",
                framework,
                capability=capability,
                effect=effect,
                arguments={"city": f"fresh-trajectory-{candidate_id.lower()}-{index + 1}"},
            )
        )
    return values


def agent_action(candidate_id: str, framework: str, subtype: str, *, internal: bool = False) -> dict[str, Any]:
    if internal:
        return action(
            candidate_id,
            framework,
            family="AGENT_SERVICE",
            subtype="DIRECT_AGENT_SERVICE",
            capability="agent.internal.20",
            agent_id=20,
            agent_capability="agent.internal.20",
            effect="READ_ONLY",
            schema=schema_one_str(),
            arguments={"task": f"fresh-internal-{candidate_id.lower()}"},
            placement="TRUSTED_MODULE_LOCAL",
        )
    return action(
        candidate_id,
        framework,
        family="AGENT_SERVICE",
        subtype=subtype,
        capability="agent.service.11",
        agent_id=11,
        agent_capability="agent.service.11",
        effect="READ_ONLY",
        schema=schema_one_str(),
        arguments={"task": f"fresh-agent-{candidate_id.lower()}"},
    )


def build_s3_universe() -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        for depth in (2, 5, 10, 20, 30, 50):
            for family, alternating in (("TOOL_SEQUENCE", False), ("ALTERNATING_TOOL_SEQUENCE", True)):
                cid = f"S3U-{framework.split()[0].upper()}-{family}-D{depth}"
                values.append({"candidate_id": cid, "framework": framework, "trajectory_family": family, "workflow": "DYNAMIC_SEQUENCE", "depth": depth, "actions": sequence_actions(cid, framework, depth, alternating), "manifest_kind": "S3_CAUSAL_TRAJECTORY", "public_profile_id": PROFILE_ID})
        for family in ("TOOL_TO_AGENT_AS_TOOL", "AGENT_AS_TOOL_TO_TOOL", "STRUCTURED_TOOL_TO_AGENT_AS_TOOL", "INTERNAL_TO_EXTERNAL", "EXTERNAL_TO_INTERNAL"):
            cid = f"S3U-{framework.split()[0].upper()}-{family}-D2"
            tool = sequence_actions(cid + "-TOOL", framework, 1)[0]
            aat = agent_action(cid + "-AAT", framework, "AGENT_AS_TOOL")
            internal = agent_action(cid + "-INTERNAL", framework, "DIRECT_AGENT_SERVICE", internal=True)
            if family == "TOOL_TO_AGENT_AS_TOOL":
                actions, workflow = [tool, aat], family
            elif family == "AGENT_AS_TOOL_TO_TOOL":
                actions, workflow = [aat, tool], family
            elif family == "STRUCTURED_TOOL_TO_AGENT_AS_TOOL":
                tool["argument_schema"] = {"schema_id": "THREE_PRIMITIVES", "fields": [{"name": "city", "primitive_type": "str"}, {"name": "count", "primitive_type": "int"}, {"name": "enabled", "primitive_type": "bool"}]}
                tool["arguments"] = {"city": "fresh-structured", "count": 17, "enabled": True}
                actions, workflow = [tool, aat], "TOOL_TO_AGENT_AS_TOOL"
            elif family == "INTERNAL_TO_EXTERNAL":
                actions, workflow = [internal, tool], family
            else:
                actions, workflow = [tool, internal], family
            values.append({"candidate_id": cid, "framework": framework, "trajectory_family": family, "workflow": workflow, "depth": 2, "actions": actions, "manifest_kind": "S3_CAUSAL_TRAJECTORY", "public_profile_id": PROFILE_ID})
    cid = "S3U-OPENAI-TOOL_TO_HANDOFF-D2"
    values.append({"candidate_id": cid, "framework": "OpenAI Agents SDK", "trajectory_family": "TOOL_TO_HANDOFF", "workflow": "TOOL_TO_HANDOFF", "depth": 2, "actions": [sequence_actions(cid + "-TOOL", "OpenAI Agents SDK", 1)[0], agent_action(cid + "-HANDOFF", "OpenAI Agents SDK", "HANDOFF")], "manifest_kind": "S3_CAUSAL_TRAJECTORY", "public_profile_id": PROFILE_ID})
    return values


def build_s4_universe() -> list[dict[str, Any]]:
    values = []
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        for effect, capability in (("READ_ONLY", "tool.read"), ("IDEMPOTENT_EFFECT", "tool.idem"), ("NON_IDEMPOTENT_EFFECT", "tool.nonidem")):
            for scenario in ("SUCCESS", "ERROR", "BOUNDED_TIMEOUT"):
                cid = f"S4U-{framework.split()[0].upper()}-{effect}-{scenario}"
                item = action(cid, framework, capability=capability, effect=effect, scenario=scenario, arguments={"city": f"fresh-effect-{effect.lower()}-{scenario.lower()}-{framework.split()[0].lower()}"})
                item.update({"candidate_id": cid, "effect_contract_origin": "SYNTHETIC_CONFIRMATORY_CONTRACT"})
                values.append(item)
    return values


def structural_arm(arm_id: str, framework: str, workflow: str, actions: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"manifest_kind": "STRUCTURAL_ARM", "arm_id": arm_id, "framework": framework, "workflow": workflow, "actions": actions, "public_profile_id": PROFILE_ID, **extra}


def build_structural_universe() -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []

    def add(stratum: str, variant: int, a: dict[str, Any], b: dict[str, Any]) -> None:
        pairs.append({"candidate_pair_id": f"SU-{stratum}-V{variant}", "stratum": stratum, "variant": variant, "arms": [a, b], "public_profile_id": PROFILE_ID})

    for variant, count in enumerate((3, 7, 13), 1):
        add("P1_AGENT_IDENTITY", variant, structural_arm(f"P1V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", sequence_actions(f"P1V{variant}A", "OpenAI Agents SDK", count)), structural_arm(f"P1V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [dict(item, agent_id=21, agent_capability="agent.workflow.21") for item in sequence_actions(f"P1V{variant}B", "OpenAI Agents SDK", count)]))
        add("P2_TOOL_ROUTE_IDENTITY", variant, structural_arm(f"P2V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", sequence_actions(f"P2V{variant}A", "OpenAI Agents SDK", count)), structural_arm(f"P2V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [action(f"P2V{variant}B-{i}", "OpenAI Agents SDK", family="EXTERNAL_HTTP", capability="external.local", effect="READ_ONLY", arguments={"city": f"fresh-route-{variant}-{i}"}) for i in range(count)]))
        add("P3_ACTION_KIND", variant, structural_arm(f"P3V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", sequence_actions(f"P3V{variant}A", "OpenAI Agents SDK", count)), structural_arm(f"P3V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [agent_action(f"P3V{variant}B-{i}", "OpenAI Agents SDK", "DIRECT_AGENT_SERVICE") for i in range(count)]))

    for variant, (low, high) in enumerate(((3, 7), (13, 29), (29, 47)), 1):
        add("P4_ACTUAL_ACTION_COUNT", variant, structural_arm(f"P4V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", sequence_actions(f"P4V{variant}A", "OpenAI Agents SDK", low)), structural_arm(f"P4V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", sequence_actions(f"P4V{variant}B", "OpenAI Agents SDK", high)))

    for variant, count in enumerate((13, 29, 47), 1):
        read = sequence_actions(f"P5V{variant}A", "OpenAI Agents SDK", count)
        varied = sequence_actions(f"P5V{variant}B", "OpenAI Agents SDK", count, True)
        add("P5_REPETITION", variant, structural_arm(f"P5V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", read), structural_arm(f"P5V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", varied))
        skew_a = sequence_actions(f"P6V{variant}A", "OpenAI Agents SDK", count)
        skew_b = sequence_actions(f"P6V{variant}B", "OpenAI Agents SDK", count)
        for index, item in enumerate(skew_a):
            if index >= max(1, count // 5):
                item.update(capability="tool.idem", effect_semantics="IDEMPOTENT_EFFECT")
        for index, item in enumerate(skew_b):
            if index < count - max(1, count // 5):
                item.update(capability="tool.idem", effect_semantics="IDEMPOTENT_EFFECT")
        add("P6_FREQUENCY_SKEW", variant, structural_arm(f"P6V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", skew_a), structural_arm(f"P6V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", skew_b))
        rare_a = sequence_actions(f"P7V{variant}A", "OpenAI Agents SDK", count)
        rare_a[(variant * 7) % count].update(capability="tool.nonidem", effect_semantics="NON_IDEMPOTENT_EFFECT")
        add("P7_RARE_TARGET", variant, structural_arm(f"P7V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", rare_a), structural_arm(f"P7V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", sequence_actions(f"P7V{variant}B", "OpenAI Agents SDK", count)))
        alternating = sequence_actions(f"P8V{variant}A", "OpenAI Agents SDK", count, True)
        grouped = sequence_actions(f"P8V{variant}B", "OpenAI Agents SDK", count)
        for index, item in enumerate(grouped):
            if index >= (count + 1) // 2:
                item.update(capability="tool.idem", effect_semantics="IDEMPOTENT_EFFECT")
        add("P8_TRANSITION_ORDER", variant, structural_arm(f"P8V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", alternating), structural_arm(f"P8V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", grouped))

    for variant, length in enumerate((8, 128, 300), 1):
        short = action(f"P9V{variant}A", "OpenAI Agents SDK", arguments={"city": "s" * length})
        long = action(f"P9V{variant}B", "OpenAI Agents SDK", arguments={"city": "l" * min(380, length + 72)})
        add("P9_PRIVATE_ARGUMENT_SIZE", variant, structural_arm(f"P9V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [short]), structural_arm(f"P9V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [long]))
        early = action(f"P10V{variant}A", "OpenAI Agents SDK", continuation={"provider_readiness_mode": "EARLY_READY"})
        late = action(f"P10V{variant}B", "OpenAI Agents SDK", continuation={"provider_readiness_mode": "LATE_READY_WITHIN_BOUND"})
        add("P10_PROVIDER_READINESS", variant, structural_arm(f"P10V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [early]), structural_arm(f"P10V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [late]))
        internal = agent_action(f"P11V{variant}A", "OpenAI Agents SDK", "DIRECT_AGENT_SERVICE", internal=True)
        external = agent_action(f"P11V{variant}B", "OpenAI Agents SDK", "DIRECT_AGENT_SERVICE")
        add("P11_INTERNAL_EXTERNAL", variant, structural_arm(f"P11V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [internal]), structural_arm(f"P11V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", [external]))
        count = (10, 20, 30)[variant - 1]
        add("P12_CAUSAL_DEPTH", variant, structural_arm(f"P12V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", sequence_actions(f"P12V{variant}A", "OpenAI Agents SDK", count)), structural_arm(f"P12V{variant}-B", "OpenAI Agents SDK", "PARALLEL_ACTIONS", sequence_actions(f"P12V{variant}B", "OpenAI Agents SDK", count)))
        tool_a = sequence_actions(f"P13V{variant}A-TOOL", "OpenAI Agents SDK", 1)[0]
        tool_b = sequence_actions(f"P13V{variant}B-TOOL", "OpenAI Agents SDK", 1)[0]
        add("P13_AGENT_SERVICE_SUBTYPE", variant, structural_arm(f"P13V{variant}-A", "OpenAI Agents SDK", "TOOL_TO_AGENT_AS_TOOL", [tool_a, agent_action(f"P13V{variant}A-AAT", "OpenAI Agents SDK", "AGENT_AS_TOOL")]), structural_arm(f"P13V{variant}-B", "OpenAI Agents SDK", "TOOL_TO_HANDOFF", [tool_b, agent_action(f"P13V{variant}B-HANDOFF", "OpenAI Agents SDK", "HANDOFF")]))
        add("P14_DYNAMIC_PRIVATE_RESOLUTION", variant, structural_arm(f"P14V{variant}-A", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", sequence_actions(f"P14V{variant}A", "OpenAI Agents SDK", 5), pir_delay_ms=0), structural_arm(f"P14V{variant}-B", "OpenAI Agents SDK", "DYNAMIC_SEQUENCE", sequence_actions(f"P14V{variant}B", "OpenAI Agents SDK", 5), pir_delay_ms=(10, 25, 50)[variant - 1]))
    return pairs


def freeze_universes(exclusions: dict[str, Any]) -> dict[str, Any]:
    s1 = build_s1_universe(exclusions)
    s2 = build_s2_universe()
    s3 = build_s3_universe()
    s4 = build_s4_universe()
    structural = build_structural_universe()
    paths = {
        "s1": ROOT / "V11A_SOURCE_TOOL_UNIVERSE.json",
        "s2": ROOT / "V11A_COMPOSITION_UNIVERSE.json",
        "s3": ROOT / "V11A_CAUSAL_TRAJECTORY_UNIVERSE.json",
        "s4": ROOT / "V11A_EFFECT_CONTRACT_UNIVERSE.json",
        "structural": ROOT / "V11A_STRUCTURAL_PAIR_UNIVERSE.json",
    }
    for key, values in (("s1", s1), ("s2", s2), ("s3", s3), ("s4", s4), ("structural", structural)):
        write_json(paths[key], {"schema": f"AgentTool.V11A.{key.upper()}CandidateUniverse/1", "seed_independent_membership": True, "candidate_count": len(values), "candidates": values})
    write_csv(
        ROOT / "V11A_SOURCE_SEMANTIC_ELIGIBLE_POOL.csv",
        [
            {
                **{key: value for key, value in item.items() if key not in {"argument_schema", "arguments"}},
                "argument_schema": json.dumps(item["argument_schema"], sort_keys=True),
                "arguments": json.dumps(item["arguments"], sort_keys=True),
                "eligible": True,
            }
            for item in s1
        ],
    )
    value = {
        "schema": "AgentTool.V11A.CandidateUniversesFreeze/1",
        "frozen_before_seed_derivation": True,
        "eligibility_uses_selection_seed": False,
        "candidate_generation_code_sha256": sha256(ROOT / "scripts" / "freeze_v11a_confirmatory.py"),
        "universes": {key: {"path": path.name, "sha256": sha256(path), "count": len(values)} for (key, path), values in zip(paths.items(), (s1, s2, s3, s4, structural), strict=True)},
    }
    value["aggregate_sha256"] = canonical_sha(value)
    write_json(UNIVERSE_FREEZE, value)
    return {"freeze": value, "s1": s1, "s2": s2, "s3": s3, "s4": s4, "structural": structural}


def derive_seeds(orchestrator: dict[str, Any], exclusions: dict[str, Any], universes: dict[str, Any]) -> dict[str, Any]:
    base_material = "|".join(
        (
            BASE_COMMIT,
            sha256(V11_4_EXECUTION_FREEZE),
            sha256(V11_4_1_BASELINE_FREEZE),
            orchestrator["aggregate_sha256"],
            exclusions["aggregate_sha256"],
            universes["freeze"]["aggregate_sha256"],
        )
    )
    value = {
        "schema": "AgentTool.V11A.SelectionSeeds/1",
        "seed_search": False,
        "v11_4_base_commit": BASE_COMMIT,
        "v11_4_freeze_manifest_sha256": sha256(V11_4_EXECUTION_FREEZE),
        "v11_4_1_baseline_freeze_sha256": sha256(V11_4_1_BASELINE_FREEZE),
        "orchestrator_aggregate_sha256": orchestrator["aggregate_sha256"],
        "master_exclusion_set_aggregate_sha256": exclusions["aggregate_sha256"],
        "candidate_universes_aggregate_sha256": universes["freeze"]["aggregate_sha256"],
        "universe_membership_frozen_before_seed_derivation": True,
        "labels": LABELS,
        "seeds": {key: sha256_bytes(f"{base_material}|{label}".encode()) for key, label in LABELS.items()},
        "derivation": "SHA256(base commit || exact V11.4 freeze bytes hash || V11.4.1 baseline || orchestrator || exclusions || seed-independent universes || fixed label)",
    }
    write_json(SEEDS, value)
    return value


def rank(seed: str, identity: str) -> str:
    return sha256_bytes(f"{seed}|{identity}".encode())


def selected_action(item: dict[str, Any], case_id: str, manifest_kind: str) -> dict[str, Any]:
    value = {key: item[key] for key in (
        "framework", "argument_schema", "arguments", "effect_semantics", "scenario", "public_profile_id"
    )}
    effect = item["effect_semantics"]
    capability = {"READ_ONLY": "tool.read", "IDEMPOTENT_EFFECT": "tool.idem", "NON_IDEMPOTENT_EFFECT": "tool.nonidem"}[effect]
    value.update(
        {
            "manifest_kind": manifest_kind,
            "case_id": case_id,
            "action_family": item.get("action_family", "TOOL"),
            "logical_action_name": item.get("logical_action_name", "v11a_" + case_id.lower().replace("-", "_")),
            "operation_id": ("op" + case_id.replace("-", ""))[:32],
            "capability": item.get("capability", capability),
            "agent_id": int(item.get("agent_id", 10)),
            "agent_capability": item.get("agent_capability", "agent.tools"),
            "agent_service_subtype": item.get("agent_service_subtype"),
            "placement": item.get("placement", "EXTERNAL"),
            "continuation": item.get("continuation", {}),
            "selected_case_executed": False,
        }
    )
    return value


def select_s1(values: list[dict[str, Any]], seed: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in values:
        grouped[item["framework"]].append(item)
    selected = []
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        per_file: Counter[str] = Counter()
        for item in sorted(grouped[framework], key=lambda value: rank(seed, value["candidate_id"])):
            if per_file[item["source_path"]] >= 2:
                continue
            selected.append(item)
            per_file[item["source_path"]] += 1
            if sum(value["framework"] == framework for value in selected) == 16:
                break
    # If a framework has a documented shortage, fill no more than the global
    # target from the other framework under the same two-site cap.
    if len(selected) < 32:
        used = {item["candidate_id"] for item in selected}
        per_file = Counter((item["framework"], item["source_path"]) for item in selected)
        for item in sorted(values, key=lambda value: rank(seed, value["candidate_id"])):
            key = (item["framework"], item["source_path"])
            if item["candidate_id"] in used or per_file[key] >= 2:
                continue
            selected.append(item); used.add(item["candidate_id"]); per_file[key] += 1
            if len(selected) == 32:
                break
    cases = []
    for index, item in enumerate(sorted(selected, key=lambda value: rank(seed, value["candidate_id"])), 1):
        case = selected_action(item, f"V11A-S1-{index:03d}", "S1_SOURCE_TOOL")
        case.update(
            {
                "candidate_id": item["candidate_id"],
                "adapter_id": item["adapter_id"],
                "source": {"path": item["source_path"], "sha256": item["source_sha256"], "line": item["source_line"], "detail": item["source_detail"]},
                "frozen_corpus_disposition": "MEDIATED",
                "effect_contract_origin": "SYNTHETIC_CONFIRMATORY_CONTRACT",
                "level": "LEVEL_A_ACTION_BOUNDARY",
            }
        )
        cases.append(case)
    return cases


def select_s2(values: list[dict[str, Any]], seed: str) -> list[dict[str, Any]]:
    selected = []
    for family in ("OPENAI_AGENT_AS_TOOL", "OPENAI_HANDOFF", "MICROSOFT_AGENT_AS_TOOL"):
        family_values = [item for item in values if item["composition_family"] == family]
        selected.extend(sorted(family_values, key=lambda item: rank(seed, item["candidate_id"]))[:4])
    cases = []
    for index, item in enumerate(sorted(selected, key=lambda value: rank(seed, value["candidate_id"])), 1):
        case = selected_action(item, f"V11A-S2-{index:03d}", "S2_COMPOSITION")
        case.update({"candidate_id": item["candidate_id"], "composition_family": item["composition_family"], "effect_contract_origin": "SYNTHETIC_CONFIRMATORY_CONTRACT", "level": "LEVEL_A_ACTION_BOUNDARY"})
        cases.append(case)
    return cases


def select_s3(values: list[dict[str, Any]], seed: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    # Predeclared mandatory deep strata, independently ranked.
    for framework, depth in (("OpenAI Agents SDK", 50), ("Microsoft Agent Framework", 30)):
        eligible = [item for item in values if item["framework"] == framework and item["depth"] == depth]
        selected.append(min(eligible, key=lambda item: rank(seed, item["candidate_id"])))
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        family_count: Counter[str] = Counter(item["trajectory_family"] for item in selected if item["framework"] == framework)
        for item in sorted((value for value in values if value["framework"] == framework), key=lambda value: rank(seed, value["candidate_id"])):
            if item in selected or family_count[item["trajectory_family"]] >= 2:
                continue
            selected.append(item); family_count[item["trajectory_family"]] += 1
            if sum(value["framework"] == framework for value in selected) == 6:
                break
    result = []
    for index, item in enumerate(sorted(selected, key=lambda value: rank(seed, value["candidate_id"])), 1):
        actions = []
        for action_index, original in enumerate(item["actions"], 1):
            value = dict(original)
            value["case_id"] = f"V11A-S3-{index:03d}-A{action_index:02d}"
            value["operation_id"] = ("op" + value["case_id"].replace("-", ""))[:32]
            value["manifest_kind"] = "S3_CAUSAL_ACTION"
            value["selected_case_executed"] = False
            actions.append(value)
        result.append({"manifest_kind": "S3_CAUSAL_TRAJECTORY", "trajectory_id": f"V11A-S3-{index:03d}", "candidate_id": item["candidate_id"], "framework": item["framework"], "trajectory_family": item["trajectory_family"], "workflow": item["workflow"], "depth": item["depth"], "actions": actions, "public_profile_id": PROFILE_ID, "selected_case_executed": False, "level": "LEVEL_A_ACTION_BOUNDARY"})
    return result


def select_s4(values: list[dict[str, Any]], seed: str) -> list[dict[str, Any]]:
    selected = []
    for effect in ("READ_ONLY", "IDEMPOTENT_EFFECT", "NON_IDEMPOTENT_EFFECT"):
        for scenario in ("SUCCESS", "ERROR", "BOUNDED_TIMEOUT"):
            eligible = [item for item in values if item["effect_semantics"] == effect and item["scenario"] == scenario]
            selected.append(min(eligible, key=lambda item: rank(seed, item["candidate_id"])))
    return [dict(selected_action(item, f"V11A-S4-{index:03d}", "S4_EFFECT_CONTRACT"), candidate_id=item["candidate_id"], effect_contract_origin="SYNTHETIC_CONFIRMATORY_CONTRACT", level="LEVEL_A_CANONICAL_EFFECT_CONTRACT") for index, item in enumerate(sorted(selected, key=lambda value: rank(seed, value["candidate_id"])), 1)]


def select_structural(values: list[dict[str, Any]], seed: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in values:
        grouped[item["stratum"]].append(item)
    result = []
    def stratum_number(value: str) -> int:
        match = re.match(r"P(\d+)_", value)
        if match is None:
            raise ValueError(f"structural stratum lacks a numeric P-prefix: {value}")
        return int(match.group(1))

    for index, stratum in enumerate(sorted(grouped, key=stratum_number), 1):
        item = min(grouped[stratum], key=lambda value: rank(seed, value["candidate_pair_id"]))
        arms = []
        for arm_index, original in enumerate(item["arms"]):
            arm = json.loads(json.dumps(original))
            arm["arm_id"] = f"V11A-P{index:02d}-{'A' if arm_index == 0 else 'B'}"
            for action_index, value in enumerate(arm["actions"], 1):
                value["case_id"] = f"{arm['arm_id']}-A{action_index:02d}"
                value["operation_id"] = ("op" + value["case_id"].replace("-", ""))[:32]
                value["manifest_kind"] = "STRUCTURAL_ACTION"
                value["selected_case_executed"] = False
            arm["selected_arm_executed"] = False
            arms.append(arm)
        result.append({"pair_id": f"V11A-P{index:02d}", "candidate_pair_id": item["candidate_pair_id"], "stratum": stratum, "arms": arms, "public_profile_id": PROFILE_ID, "selected_pair_executed": False})
    return result


def freeze_manifests(universes: dict[str, Any], seeds: dict[str, Any]) -> dict[str, Any]:
    s1 = select_s1(universes["s1"], seeds["seeds"]["s1"])
    s2 = select_s2(universes["s2"], seeds["seeds"]["s2"])
    s3 = select_s3(universes["s3"], seeds["seeds"]["s3"])
    s4 = select_s4(universes["s4"], seeds["seeds"]["s4"])
    structural = select_structural(universes["structural"], seeds["seeds"]["structural"])
    manifests = {
        "s1": (ROOT / "V11A_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json", {"schema": "AgentTool.V11A.SourceSemanticHoldoutFreeze/1", "selected_holdout_executed": False, "cases": s1}),
        "s2": (ROOT / "V11A_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json", {"schema": "AgentTool.V11A.CompositionSemanticHoldoutFreeze/1", "selected_holdout_executed": False, "microsoft_handoff": "NATIVE_MECHANISM_ABSENT", "cases": s2}),
        "s3": (ROOT / "V11A_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json", {"schema": "AgentTool.V11A.CausalTrajectoryHoldoutFreeze/1", "selected_holdout_executed": False, "trajectories": s3}),
        "s4": (ROOT / "V11A_EFFECT_CONTRACT_HOLDOUT_FREEZE.json", {"schema": "AgentTool.V11A.EffectContractHoldoutFreeze/1", "selected_holdout_executed": False, "cases": s4}),
        "structural": (ROOT / "V11A_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json", {"schema": "AgentTool.V11A.StructuralSizeHoldoutFreeze/1", "selected_holdout_executed": False, "public_profile_id": PROFILE_ID, "pairs": structural}),
    }
    for path, value in manifests.values():
        write_json(path, value)

    def semantic_rows(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"case_id": item["case_id"], "framework": item["framework"], "family": item.get("composition_family", item["manifest_kind"]), "effect_semantics": item["effect_semantics"], "scenario": item["scenario"], "source_path": item.get("source", {}).get("path", "SYNTHETIC_GENERIC"), "source_line": item.get("source", {}).get("line", ""), "executed": "NO"} for item in cases]

    write_csv(ROOT / "V11A_SOURCE_SEMANTIC_HOLDOUT_CASES.csv", semantic_rows(s1))
    write_csv(ROOT / "V11A_COMPOSITION_SEMANTIC_HOLDOUT_CASES.csv", semantic_rows(s2))
    write_csv(ROOT / "V11A_EFFECT_CONTRACT_HOLDOUT_CASES.csv", semantic_rows(s4))
    write_csv(ROOT / "V11A_CAUSAL_TRAJECTORY_HOLDOUT_CASES.csv", [{"trajectory_id": item["trajectory_id"], "framework": item["framework"], "family": item["trajectory_family"], "depth": item["depth"], "action_count": len(item["actions"]), "executed": "NO"} for item in s3])
    write_csv(ROOT / "V11A_STRUCTURAL_SIZE_HOLDOUT_PAIRS.csv", [{"pair_id": item["pair_id"], "stratum": item["stratum"], "candidate_pair_id": item["candidate_pair_id"], "arm_a": item["arms"][0]["arm_id"], "arm_b": item["arms"][1]["arm_id"], "executed": "NO"} for item in structural])

    # Loader-only validation: no runtime API is invoked here.
    loaded = 0
    for item in s1 + s2 + s4:
        load_semantic_case(item); loaded += 1
    for item in s3:
        load_trajectory_case(item); loaded += 1
    for pair in structural:
        for arm in pair["arms"]:
            load_structural_arm(arm); loaded += 1
    return {"manifests": manifests, "s1": s1, "s2": s2, "s3": s3, "s4": s4, "structural": structural, "loadable": loaded}


def freeze_rules() -> list[Path]:
    paths = []
    texts = {
        "V11A_SEMANTIC_DECISION_RULES.md": """# V11A semantic decision rules

Each selected semantic case runs exactly one native reference and one canonical path in future V11B. Frozen classes are `PASS`, `SEMANTIC_MISMATCH`, `NATIVE_REFERENCE_FAIL`, `CANONICAL_FUNCTIONAL_FAIL`, `PROFILE_ADMISSION_CLOSED`, `INFRASTRUCTURE_SCHEDULE_FAILURE`, `TRANSPORT_FAILURE`, and `HARNESS_INTEGRITY_FAILURE`. No case may be omitted, replaced, or retried. S1 establishes only Level-A action-boundary fidelity; its synthetic effect contract is not attributed to the original Tool body. S4 separately tests generic canonical effect contracts. Chain-of-thought is never compared.
""",
        "V11A_STRUCTURAL_DECISION_RULES.md": """# V11A structural decision rules

Both arms must first be functionally valid: expected operations admitted, provider semantics observed, framework results delivered, no missing/unexpected/duplicate result, zero dummy heavy operations, overflow, scheduler miss, and silent committed-result loss, and session status `COMPLETE`. Otherwise the result is `INVALID_FUNCTIONAL_PAIR`, never privacy PASS. Exact equality uses the one frozen V11.4 profile, authenticated session/slot order, stronger structural projection, and actual Relay-derived size projection. Timestamps and ephemeral ports are excluded. Timing privacy remains open.
""",
        "V11A_PREFIX_RULES.md": """# V11A prefix rules

For every functionally valid pair, exact structural prefixes are compared at rounds `1, 10, 50, 100, 200, 300, 356`. Prefixes are normalized by authenticated public session/slot order. No actual timestamp participates.
""",
        "V11A_ONE_SHOT_EXECUTION_POLICY.md": """# V11A one-shot execution policy

Future V11B executes every selected native reference once, every canonical semantic/trajectory case once, and every structural arm once in frozen order. There is no automatic retry, result replacement, profile tuning, reordering, or case substitution. Infrastructure, admission, schedule, transport, and integrity failures retain their frozen failure class.
""",
        "V11A_APPEND_ONLY_EVIDENCE_CONTRACT.md": """# V11A append-only evidence contract

Future output root `results_v11b_confirmatory` must be newly created and refuse overwrite. Each run preserves its frozen input, native and canonical semantic records, private trajectory projection, SimplePIR and descriptor evidence, trusted route evidence, raw Relay events, slot-launch diagnostics, provider observations, recovery journal, DeliveryLedger, Go result, structural/size projections, and functional/semantic verdicts. Summaries are derived only from immutable raw records. No such output is created in V11A.
""",
    }
    for name, text in texts.items():
        path = ROOT / name; write_text(path, text); paths.append(path)
    return paths


def freeze_order(selected: dict[str, Any], seed: str) -> dict[str, Any]:
    semantic_ids = [item["case_id"] for group in (selected["s1"], selected["s2"], selected["s4"]) for item in group]
    trajectory_ids = [item["trajectory_id"] for item in selected["s3"]]
    arm_ids = [arm["arm_id"] for pair in selected["structural"] for arm in pair["arms"]]
    value = {
        "schema": "AgentTool.V11A.ExecutionOrder/1",
        "semantic_case_order": sorted(semantic_ids, key=lambda value: rank(seed, value)),
        "causal_trajectory_order": sorted(trajectory_ids, key=lambda value: rank(seed, value)),
        "structural_arm_order": sorted(arm_ids, key=lambda value: rank(seed, value)),
        "arm_a_always_first": False,
        "selected_holdout_cases_executed": 0,
    }
    write_json(ROOT / "V11A_EXECUTION_ORDER.json", value)
    return value


def final_freeze(audit, environment, orchestrator, exclusions, universes, seeds, selected, rule_paths, order) -> dict[str, Any]:
    bound = [
        V11_4_EXECUTION_FREEZE,
        V11_4_1_BASELINE_FREEZE,
        RESTART_AUDIT,
        ENVIRONMENT_FREEZE,
        ORCHESTRATOR_FREEZE,
        EXCLUSION_SET,
        UNIVERSE_FREEZE,
        SEEDS,
        PROFILE,
        ROOT / "V11A_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json",
        ROOT / "V11A_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json",
        ROOT / "V11A_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json",
        ROOT / "V11A_EFFECT_CONTRACT_HOLDOUT_FREEZE.json",
        ROOT / "V11A_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json",
        ROOT / "v11a_confirmatory" / "orchestrator.py",
        ROOT / "v11a_confirmatory" / "projection.py",
        ROOT / "v11_full_scope" / "models.py",
        ROOT / "v11_full_scope" / "frameworks.py",
        ROOT / "v11_full_scope" / "structural.py",
        ROOT / "v11_online" / "frameworks.py",
        ROOT / "canonical_v9_1" / "projection.py",
        *rule_paths,
        ROOT / "V11A_EXECUTION_ORDER.json",
    ]
    value = {
        "schema": "AgentTool.V11A.FinalConfirmatoryFreeze/1",
        "status": "FROZEN_NO_SELECTED_EXECUTION",
        "v11_4_base_commit": BASE_COMMIT,
        "v11_4_freeze_manifest_sha256": sha256(V11_4_EXECUTION_FREEZE),
        "canonical_linux_binary_sha256": environment["canonical_linux_binary_sha256"],
        "bound_files": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in bound},
        "counts": {
            "s1": len(selected["s1"]),
            "s2": len(selected["s2"]),
            "s3": len(selected["s3"]),
            "s4": len(selected["s4"]),
            "structural_pairs": len(selected["structural"]),
            "loadable_specs": selected["loadable"],
        },
        "all_selected_manifests_loadable_with_frozen_executor": "PASS",
        "protected_implementation_changed": False,
        "seed_search": False,
        "selected_holdout_cases_executed": 0,
        "selected_semantic_runtime_results": 0,
        "selected_trajectory_runtime_results": 0,
        "selected_structural_relay_traces": 0,
        "timing_privacy": "OPEN / NOT TESTED",
        "packet_level_timing": "OPEN",
        "hardware_tee": "NOT_TESTED",
    }
    value["aggregate_sha256"] = canonical_sha(value)
    write_json(ROOT / "V11A_FINAL_CONFIRMATORY_FREEZE.json", value)
    return value


def audit_report(exclusions, universes, selected, final) -> None:
    s1_counts = Counter(item["framework"] for item in selected["s1"])
    s2_counts = Counter(item["composition_family"] for item in selected["s2"])
    s3_framework = Counter(item["framework"] for item in selected["s3"])
    s3_family = Counter(item["trajectory_family"] for item in selected["s3"])
    s3_depth = Counter(int(item["depth"]) for item in selected["s3"])
    structural = {item["stratum"] for item in selected["structural"]}
    text = f"""# V11A fresh full-scope confirmatory holdout freeze audit

Status: **FREEZE COMPLETE; SELECTED EXECUTION = 0**.

- V11.4 base commit: `{BASE_COMMIT}`
- V11.4 exact execution-freeze SHA-256: `{sha256(V11_4_EXECUTION_FREEZE)}`
- Protected implementation paths: {json.loads(RESTART_AUDIT.read_text())['protected_path_count']}/{json.loads(RESTART_AUDIT.read_text())['protected_path_count']} match the base commit.
- Master exclusions: {exclusions['counts']['exact_source_sites']} exact source sites, {exclusions['counts']['whole_source_files']} whole files, {exclusions['counts']['workload_signatures']} workload signatures.
- Seed search: **NO**. All candidate universes were frozen before seed derivation.
- S1 eligible/selected: {len(universes['s1'])}/{len(selected['s1'])}; framework balance {dict(s1_counts)}.
- S2 selected: {len(selected['s2'])}, by family {dict(s2_counts)}. Microsoft handoff remains `NATIVE_MECHANISM_ABSENT`.
- S3 selected: {len(selected['s3'])}, frameworks {dict(s3_framework)}, families {dict(s3_family)}, depths {dict(sorted(s3_depth.items()))}. Depth 30 and 50 are present.
- S4 generic effect-contract cases: {len(selected['s4'])}; these are Level-A synthetic confirmatory contracts, not original source Tool semantics.
- Structural pairs: {len(selected['structural'])}; internal/external, causal-depth, and Agent-service-subtype strata are present: {all(item in structural for item in ('P11_INTERNAL_EXTERNAL', 'P12_CAUSAL_DEPTH', 'P13_AGENT_SERVICE_SUBTYPE'))}.
- All selected manifests loadable without runtime invocation: **PASS** ({selected['loadable']} specifications).
- Selected semantic outcomes, trajectory outcomes, Relay traces, and privacy CSVs: **0**.

Timing privacy remains `OPEN / NOT TESTED`, packet-level timing remains `OPEN`, hardware TEE remains `NOT_TESTED`, action mediation coverage remains `894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED`, and source-body executable subset remains `0`. No overall privacy GO is issued. V11B was not run.
"""
    write_text(ROOT / "V11A_FREEZE_AUDIT.md", text)


def main() -> None:
    forbidden_existing = [
        ORCHESTRATOR_FREEZE,
        EXCLUSION_SET,
        UNIVERSE_FREEZE,
        SEEDS,
        ROOT / "V11A_FINAL_CONFIRMATORY_FREEZE.json",
    ]
    if any(path.exists() for path in forbidden_existing):
        raise FileExistsError("V11A restart freeze artifacts already exist; refusing overwrite")
    audit = freeze_preselection_audit()
    environment = freeze_environment()
    orchestrator = freeze_orchestrator()
    exclusions = master_exclusions()
    universes = freeze_universes(exclusions)
    seeds = derive_seeds(orchestrator, exclusions, universes)
    selected = freeze_manifests(universes, seeds)
    rules = freeze_rules()
    order = freeze_order(selected, seeds["seeds"]["order"])
    final = final_freeze(audit, environment, orchestrator, exclusions, universes, seeds, selected, rules, order)
    audit_report(exclusions, universes, selected, final)
    print(f"S1_POOL={len(universes['s1'])} S1_SELECTED={len(selected['s1'])}")
    print(f"S2_SELECTED={len(selected['s2'])} S3_SELECTED={len(selected['s3'])} S4_SELECTED={len(selected['s4'])}")
    print(f"STRUCTURAL_PAIRS={len(selected['structural'])}")
    print("ALL_SELECTED_MANIFESTS_LOADABLE_WITH_FROZEN_EXECUTOR=PASS")
    print("SELECTED_HOLDOUT_CASES_EXECUTED=0")


if __name__ == "__main__":
    main()

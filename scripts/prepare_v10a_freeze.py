from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import random
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results_v10a"
DRAFTS = RESULTS / "freeze_drafts"
PROFILE_ID = "V10-STRICT-H50-C1"
V9_AGG = "c53925ed1036798f773e6d10588258bb365a69368c04e5cb5403b2f5128b9a46"
FRAMEWORK_ROOT = {
    "OpenAI Agents SDK": ROOT / "external_stage10" / "openai-agents-python",
    "Microsoft Agent Framework": ROOT / "external_stage9" / "agent-framework",
}
PRIOR_FILES = [
    "ACTION_SEMANTIC_HOLDOUT_V6.csv", "ACTION_SEMANTIC_HOLDOUT_V7.csv",
    "CANONICAL_ACTION_SEMANTIC_HOLDOUT_V8.csv", "CANONICAL_SEMANTIC_HOLDOUT_V9.csv",
    "SEMANTIC_HOLDOUT_V2_RESULTS.csv", "SEMANTIC_HOLDOUT_V3_RESULTS.csv",
    "SEMANTIC_FIDELITY_V2_DEVELOPMENT_REGRESSION_20260828.csv",
    "DEVELOPMENT_PAIR_PRECHECK_V9_1.csv",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader(); w.writerows(rows)


def profile() -> dict[str, Any]:
    return {
        "schema": "AgentTool.V10StrictPublicCapacityProfile/1", "profile_id": PROFILE_ID,
        "phase": "V10_CONFIRMATORY_FREEZE", "public_profile_revision": 1, "maximum_real_operations": 50,
        "admission_rounds": 50, "total_rounds": 111, "session_count": 1,
        "round_period_ms": 5, "provider_completion_bound_ms": 50, "terminal_rounds": 1,
        "request_bhttp_bytes": 1024, "response_bhttp_bytes": 768,
        "final_request_bytes": 1079, "final_response_bytes": 800,
        "ohttp_key_id": 7, "kem_id": 32, "kdf_id": 1, "aead_id": 1, "config_epoch": 3,
        "relay_endpoint_class": "LOCAL_RELAY", "gateway_endpoint_class": "LOCAL_GATEWAY",
        "connection_policy": "ONE_PERSISTENT_KEEP_ALIVE_CONNECTION_PER_PUBLIC_SESSION",
        "scheduled_start_policy": "PUBLIC_SESSION_ACCEPT_MONOTONIC_T0",
        "scheduled_lifetime_ms": 555, "scheduled_lifetime_ns": 555_000_000,
        "privacy_relevant_parameters_selected_before_private_workloads": True,
        "timing_privacy": "OPEN / NOT TESTED",
    }


def write_environment() -> None:
    evidence = RESULTS / "linux_preholdout_regression"
    env = (evidence / "environment.txt").read_text(encoding="utf-8")
    binary_line = (evidence / "binary_sha256.txt").read_text().strip()
    binary_sha = binary_line.split()[0]
    ohttp = json.loads((ROOT / "OHTTP_VENDOR_PROVENANCE_V9.json").read_text())
    system = json.loads((ROOT / "V10_PRE_HOLDOUT_SYSTEM_FREEZE.json").read_text())
    common = {
        "schema": "AgentTool.V10EnvironmentFreeze/1", "created_utc": now(),
        "authorized_host_role": "offline Linux build/regression host", "selected_holdout_executed": False,
        "os": "Ubuntu 22.04.5 LTS", "kernel": "5.15.0-94-generic", "architecture": "x86_64",
        "cpu_model": "Intel(R) Xeon(R) Platinum 8470Q", "python": "3.12.3",
        "go": "go1.26.5 linux/amd64", "gcc": "11.4.0", "cryptography": "42.0.5",
        "numpy": "2.4.6", "scikit_learn": "NOT_INSTALLED (not required for freeze-only regressions)",
        "simplepir_commit": "e9020b03bf2872c75b8954e749e32408b5db87ed",
        "ohttp_source_tree_sha256": ohttp["source_tree_sha256"],
        "canonical_source_tree_sha256": system["components"]["canonical_runner"]["aggregate_sha256"],
        "raw_environment_log_sha256": sha_file(evidence / "environment.txt"),
        "regressions": {
            "python": "27 passed", "go_workspace": "PASS", "rfc9458": "PASS with go test -vet=off",
            "rfc9458_vet_note": "Go 1.26 vet rejects upstream test Fatalf with a non-constant format string; production source was unchanged.",
            "rfc9292": "PASS", "simplepir_descriptor_smoke": "PASS rows=2", "v9_1_profile_projection": "PASS",
        },
    }
    write_json(ROOT / "V10_ENVIRONMENT_FREEZE.json", common)
    provenance = {
        "schema": "AgentTool.V10CanonicalBinaryProvenance/1", "created_utc": now(),
        "source_freeze": "V10_PRE_HOLDOUT_SYSTEM_FREEZE.json", "source_freeze_sha256": sha_file(ROOT / "V10_PRE_HOLDOUT_SYSTEM_FREEZE.json"),
        "input_archive_sha256": "508ffb4f36b324919b9d1b54af2f013a8b37bd8194faf8279c1e426a4773f20e",
        "executable_sha256": binary_sha, "target": "linux/amd64",
        "build_command": "GO111MODULE=off go build -trimpath -o canonical-v9-runner common-action-gateway-v2/cmd/canonical-v9-runner",
        "build_environment": {"GOPATH": "isolated copied source tree", "GO111MODULE": "off", "GOPROXY": "off", "GOSUMDB": "off"},
        "dependency_resolution": "GOPATH copy plus ohttp-go vendored dependencies; no network resolution",
        "old_transferred_binary_used": False, "selected_holdout_executed": False,
        "evidence_archive_sha256": sha_file(evidence / "v10a_linux_evidence.tgz"),
    }
    write_json(ROOT / "V10_CANONICAL_BINARY_PROVENANCE.json", provenance)


def write_profile_and_seeds() -> tuple[str, str]:
    p = profile(); write_json(ROOT / "PUBLIC_PROFILE_V10.json", p)
    v9 = {
        "maximum_real_operations": 50, "admission_rounds": 50, "total_rounds": 111,
        "session_count": 1, "round_period_ms": 5, "provider_completion_bound_ms": 50,
        "terminal_rounds": 1, "request_bhttp_bytes": 1024, "response_bhttp_bytes": 768,
        "final_request_bytes": 1079, "final_response_bytes": 800, "ohttp_key_id": 7,
        "kem_id": 32, "kdf_id": 1, "aead_id": 1, "config_epoch": 3,
        "relay_endpoint_class": "LOCAL_RELAY", "gateway_endpoint_class": "LOCAL_GATEWAY",
        "connection_policy": "ONE_PERSISTENT_KEEP_ALIVE_CONNECTION_PER_PUBLIC_SESSION",
        "scheduled_lifetime_ms": 555,
    }
    diff = {k: {"v9_1": v9[k], "v10": p[k], "equal": v9[k] == p[k]} for k in v9}
    write_json(ROOT / "PUBLIC_PROFILE_V10_VS_V9_1_DIFF.json", {
        "schema": "AgentTool.V10VsV9_1SecurityProfileDiff/1", "all_security_relevant_values_equal": all(x["equal"] for x in diff.values()),
        "allowed_metadata_differences": {"profile_id": {"v9_1": "V9_1-STRICT-H50-P1", "v10": PROFILE_ID}, "phase": "development -> confirmatory freeze"},
        "security_relevant_fields": diff,
    })
    sem = sha_bytes((V9_AGG + "AgentTool-V10-semantic-v1").encode())
    structural = sha_bytes((V9_AGG + "AgentTool-V10-structural-v1").encode())
    write_json(ROOT / "V10_SELECTION_SEEDS.json", {
        "schema": "AgentTool.V10SelectionSeeds/1", "base_v9_functional_freeze_aggregate": V9_AGG,
        "semantic_label": "AgentTool-V10-semantic-v1", "semantic_seed_sha256": sem,
        "structural_label": "AgentTool-V10-structural-v1", "structural_seed_sha256": structural,
        "seed_search_performed": False,
    })
    return sem, structural


def norm_prior_path(value: str) -> tuple[str | None, str]:
    s = value.replace("\\", "/")
    if "external_stage10/openai-agents-python/" in s:
        return "OpenAI Agents SDK", s.split("external_stage10/openai-agents-python/", 1)[1]
    if "external_stage9/agent-framework/" in s:
        return "Microsoft Agent Framework", s.split("external_stage9/agent-framework/", 1)[1]
    return None, s


def exclusions() -> tuple[set[tuple[str, str, str]], list[dict[str, Any]]]:
    exact: set[tuple[str, str, str]] = set(); records: list[dict[str, Any]] = []
    for name in PRIOR_FILES:
        path = ROOT / name
        if not path.exists(): continue
        try:
            rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        except Exception:
            continue
        for row in rows:
            raw = row.get("source_path") or row.get("path") or ""
            if not raw: continue
            framework = row.get("framework") or norm_prior_path(raw)[0]
            _, rel = norm_prior_path(raw)
            line = row.get("source_line") or row.get("line") or row.get("source_location") or "*"
            key = (str(framework), rel, str(line))
            exact.add(key)
            records.append({"framework": framework, "source_path": rel, "source_location": str(line), "prior_artifact": name, "exclusion_scope": "exact site when line known; source file when line unavailable"})
    # Conservative file exclusions when prior artifacts did not retain a line.
    file_keys = {(f, p) for f, p, line in exact if line in {"", "*", "None"}}
    out = {"schema": "AgentTool.V10SemanticExclusionSet/1", "created_before_selection": True,
           "prior_artifacts": PRIOR_FILES, "record_count": len(records), "records": sorted(records, key=lambda x: (str(x["framework"]), x["source_path"], x["source_location"]))}
    write_json(ROOT / "V10_SEMANTIC_EXCLUSION_SET.json", out)
    return exact | {(f, p, "FILE") for f, p in file_keys}, records


def candidate_pool(seed: str, excluded: set[tuple[str, str, str]]) -> list[dict[str, Any]]:
    rows = list(csv.DictReader((ROOT / "ACTION_MEDIATION_CORPUS_V6.csv").open(encoding="utf-8")))
    seen: set[tuple[str, str, str, str, str]] = set(); eligible = []
    file_excluded = {(f, p) for f, p, line in excluded if line == "FILE"}
    for row in rows:
        # The frozen V6 file spells its fully-mediated disposition MEDIATED (894 rows).
        if row["v6_disposition"] != "MEDIATED": continue
        key = (row["framework"], row["relative_path"], row["line"], row["action_site_kind"], row["detail"])
        if key in seen: continue
        seen.add(key)
        source = FRAMEWORK_ROOT[row["framework"]] / row["relative_path"]
        if not source.is_file(): continue
        if (row["framework"], row["relative_path"]) in file_excluded or (row["framework"], row["relative_path"], row["line"]) in excluded:
            continue
        score = sha_bytes((seed + "|" + "|".join(key)).encode())
        eligible.append({
            "framework": row["framework"], "pinned_commit": row["pinned_commit"],
            "source_path": row["relative_path"], "source_line": int(row["line"]),
            "source_sha256": sha_file(source), "action_family": row["action_site_kind"],
            "source_detail": row["detail"], "original_v6_disposition": "MEDIATED",
            "eligibility_interpretation": "FULLY_MEDIATED equivalent in frozen V6 schema",
            "local_deterministic_adapter": "ACTION_BOUNDARY_LOCAL_ADAPTER",
            "external_network_or_credentials": False, "native_projection_well_defined": True,
            "canonical_projection_well_defined": True, "deterministic_score": score,
        })
    eligible.sort(key=lambda x: x["deterministic_score"])
    fields = list(eligible[0])
    write_csv(ROOT / "V10_SEMANTIC_ELIGIBLE_POOL.csv", eligible, fields)
    (ROOT / "V10_SEMANTIC_ELIGIBLE_POOL_HASH.txt").write_text(sha_file(ROOT / "V10_SEMANTIC_ELIGIBLE_POOL.csv") + "\n", encoding="utf-8")
    return eligible


def select_cases(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []; per_file = Counter()
    requirements = {
        "OpenAI Agents SDK": [("handoff", 2), ("agents_as_tools", 2), ("tool", 12)],
        "Microsoft Agent Framework": [("agents_as_tools", 2), ("tool", 14)],
    }
    used = set()
    for fw, groups in requirements.items():
        for family, count in groups:
            values = [x for x in pool if x["framework"] == fw and x["action_family"] == family]
            for item in values:
                k = (fw, item["source_path"], item["source_line"], item["source_detail"])
                if k in used or per_file[(fw, item["source_path"])] >= 2: continue
                selected.append(item); used.add(k); per_file[(fw, item["source_path"])] += 1
                if sum(1 for x in selected if x["framework"] == fw and x["action_family"] == family) >= count: break
        # The frozen Microsoft eligible pool has too few distinct source files
        # to reach sixteen under a strict two-site cap. Fill deterministically
        # with a third site only after exhausting the preferred cap.
        while sum(1 for x in selected if x["framework"] == fw) < 16:
            item = next((x for x in pool if x["framework"] == fw
                         and (fw, x["source_path"], x["source_line"], x["source_detail"]) not in used
                         and per_file[(fw, x["source_path"])] < 3), None)
            if item is None: break
            k = (fw, item["source_path"], item["source_line"], item["source_detail"])
            selected.append(item); used.add(k); per_file[(fw, item["source_path"])] += 1
    if len(selected) != 32 or any(sum(1 for x in selected if x["framework"] == fw) != 16 for fw in requirements):
        raise RuntimeError(f"deterministic strata could not select 32 cases: {Counter(x['framework'] for x in selected)}")
    scenarios = [
        ("READ_ONLY_SUCCESS", "READ_ONLY", "SUCCESS"),
        ("IDEMPOTENT_EFFECT_SUCCESS", "IDEMPOTENT_EFFECT", "SUCCESS"),
        ("READ_ONLY_ERROR", "READ_ONLY", "ERROR"),
        ("READ_ONLY_TIMEOUT", "READ_ONLY", "TIMEOUT"),
        ("MULTI_ACTION_READ_ONLY", "READ_ONLY", "SUCCESS"),
        ("IDEMPOTENT_EFFECT_ERROR", "IDEMPOTENT_EFFECT", "ERROR"),
        ("NON_IDEMPOTENT_SUCCESS", "NON_IDEMPOTENT_EFFECT", "SUCCESS"),
        ("READ_ONLY_SUCCESS_ALT", "READ_ONLY", "SUCCESS"),
    ]
    cases = []
    for i, item in enumerate(sorted(selected, key=lambda x: x["deterministic_score"]), 1):
        scenario, effect, outcome = scenarios[(i - 1) % len(scenarios)]
        op_count = 2 if scenario == "MULTI_ACTION_READ_ONLY" else 1
        opids = [f"v10s{i:04d}{j:04d}" for j in range(1, op_count + 1)]
        cases.append({
            "case_id": f"V10S-{i:03d}", "selection_rank": i, "framework": item["framework"],
            "pinned_commit": item["pinned_commit"], "source": {"path": item["source_path"], "sha256": item["source_sha256"], "line": item["source_line"], "detail": item["source_detail"]},
            "action_family": item["action_family"], "deterministic_scenario": scenario,
            "deterministic_test_input": {"prompt": f"local-v10-input-{i:03d}", "protected_argument": f"argument-{i:03d}"},
            "local_provider_configuration": {"provider": "V10_DETERMINISTIC_LOCAL_PROVIDER", "outcome": outcome, "response_token": f"local-result-{i:03d}", "timeout_is_local_and_bounded": outcome == "TIMEOUT"},
            "declared_effect_semantics": effect,
            "comparison_projection_schema": list(("selected_logical_action", "arguments", "provider_visible_logical_request", "effect_count", "operation_outcome_semantics", "result", "final_framework_visible_result_state")),
            "public_profile_id": PROFILE_ID, "operation_ids": opids,
            "expected_runtime_answer_frozen": False,
        })
    return cases


def action(opid: str, kind: str, capability: str, route: str, semantics: str, payload: str) -> dict[str, Any]:
    return {"operation_id": opid, "action_kind": kind, "capability": capability, "private_route_identity": route, "effect_semantics": semantics, "protected_argument": payload}


def structural_pairs(seed: str) -> list[dict[str, Any]]:
    counter = 1
    def arm(arm_id: str, agent: int, cap: str, specs: list[tuple[str,str,str,str,str]]) -> dict[str, Any]:
        nonlocal counter
        acts=[]
        for kind, capability, route, semantics, payload in specs:
            opid=f"v10p{counter:08d}"; counter += 1
            acts.append(action(opid,kind,capability,route,semantics,payload))
        return {"arm_id": arm_id, "public_profile_id": PROFILE_ID, "private_agent_id": agent, "private_agent_capability": cap, "actual_real_action_count": len(acts), "private_actions": acts}
    tool_read=("TOOL","tool.read","route-tool-read","READ_ONLY","v10")
    tool_idem=("TOOL","tool.idem","route-tool-idem","IDEMPOTENT_EFFECT","v10")
    rare=("TOOL","tool.nonidem","route-tool-nonidem","NON_IDEMPOTENT_EFFECT","v10")
    pairs=[]
    def add(pid,name,a,b,notes=""): pairs.append({"pair_id":pid,"stratum":name,"selection_method":"deterministic from structural_seed","structural_seed":seed,"notes":notes,"arms":[a,b]})
    add("S1","AGENT_IDENTITY",arm("S1-A",1,"agent.a",[("TOOL","tool.a","route-tool-a","READ_ONLY",f"a{i}") for i in range(9)]),arm("S1-B",2,"agent.b",[("TOOL","tool.b","route-tool-b","IDEMPOTENT_EFFECT",f"b{i}") for i in range(9)]))
    add("S2","ACTION_TARGET_DESTINATION",arm("S2-A",10,"agent.tools",[tool_read]*11),arm("S2-B",10,"agent.tools",[("EXTERNAL_HTTP","external.local","route-external-local","READ_ONLY","v10")]*11))
    add("S3","ACTION_KIND",arm("S3-A",10,"agent.tools",[tool_read]*13),arm("S3-B",11,"agent.service.11",[("AGENT_SERVICE","agent.service.11","route-agent-11","READ_ONLY","v10")]*13))
    add("S4","PRIVATE_ACTION_COUNT",arm("S4-A",10,"agent.tools",[tool_read]*7),arm("S4-B",10,"agent.tools",[tool_read]*43))
    varied=[tool_read,tool_idem,("EXTERNAL_HTTP","external.local","route-external-local","READ_ONLY","v10"),rare]
    add("S5","REPETITION_PATTERN",arm("S5-A",10,"agent.tools",[tool_read]*24),arm("S5-B",10,"agent.tools",[varied[i%4] for i in range(24)]))
    add("S6","FREQUENCY_SKEW",arm("S6-A",10,"agent.tools",[tool_read]*26+[tool_idem]*4),arm("S6-B",10,"agent.tools",[tool_read]*4+[tool_idem]*26))
    rare_pos=int(seed[:8],16)%31
    seq=[tool_read]*31; seq[rare_pos]=rare
    add("S7","RARE_TARGET",arm("S7-A",10,"agent.tools",seq),arm("S7-B",10,"agent.tools",[tool_read]*31),f"seeded rare zero-based position={rare_pos}")
    add("S8","TRANSITION_PATTERN",arm("S8-A",10,"agent.tools",[tool_read if i%2==0 else tool_idem for i in range(32)]),arm("S8-B",10,"agent.tools",[tool_read]*16+[tool_idem]*16))
    add("S9","PRIVATE_ARGUMENT_LENGTH",arm("S9-A",10,"agent.tools",[("TOOL","tool.read","route-tool-read","READ_ONLY","s"*8)]*12),arm("S9-B",10,"agent.tools",[("TOOL","tool.read","route-tool-read","READ_ONLY","l"*512)]*12))
    add("S10","COMPLETION_BEHAVIOR",arm("S10-A",10,"agent.tools",[tool_read]*14),arm("S10-B",13,"agent.service.13",[("AGENT_SERVICE","agent.service.13","route-agent-13","NON_IDEMPOTENT_EFFECT","v10")]*14),"validated local providers have 0-2ms vs 3-12ms service distributions, both below public 50ms completion bound; timing is not a privacy verdict")
    return pairs


def prepare() -> None:
    RESULTS.mkdir(exist_ok=True); DRAFTS.mkdir(exist_ok=True)
    if not (ROOT / "V10_PRE_HOLDOUT_SYSTEM_FREEZE.json").exists(): raise SystemExit("system freeze must exist first")
    write_environment(); sem_seed, struct_seed = write_profile_and_seeds()
    excluded,_=exclusions(); pool=candidate_pool(sem_seed,excluded); cases=select_cases(pool); pairs=structural_pairs(struct_seed)
    availability = Counter((x["framework"], x["action_family"]) for x in pool)
    file_concentration = Counter((c["framework"], c["source"]["path"]) for c in cases)
    semantic={"schema":"AgentTool.CanonicalSemanticHoldoutV10Freeze/1","phase":"V10A_FREEZE_ONLY","selected_holdout_executed":False,"selection_seed":sem_seed,"selection_rule":"lowest deterministic score within predeclared framework/family strata; preferred cap two sites per source file, relaxed to three only where the frozen pool could not reach the framework quota","target_cases":32,
              "eligible_stratum_counts": {f"{k[0]}|{k[1]}": v for k,v in sorted(availability.items())},
              "documented_shortages": ["Microsoft Agent Framework agents_as_tools: 0 fresh eligible sites after prior-case exclusion"],
              "source_file_cap_exception": {"maximum_selected_sites": max(file_concentration.values()), "reason": "Microsoft framework quota could not reach 16 under the preferred two-site cap after exclusions"},
              "cases":cases}
    structural={"schema":"AgentTool.StructuralSizeHoldoutV10Freeze/1","phase":"V10A_FREEZE_ONLY","selected_holdout_executed":False,"public_profile_id":PROFILE_ID,"internal_external_stratum":"NOT_APPLICABLE","pairs":pairs}
    write_json(DRAFTS/"semantic.json",semantic); write_json(DRAFTS/"structural.json",structural)
    ids=[i for c in cases for i in c["operation_ids"]]+[a["operation_id"] for p in pairs for armv in p["arms"] for a in armv["private_actions"]]
    if len(ids)!=len(set(ids)): raise AssertionError("global operation ID collision")
    write_json(RESULTS/"operation_id_abi_input.json",{"operation_ids":ids})
    print(f"PREPARED pool={len(pool)} cases={len(cases)} pairs={len(pairs)} ids={len(ids)}")


def finalize(abi_evidence: Path) -> None:
    abi_evidence = abi_evidence.resolve()
    if not abi_evidence.is_file() or not abi_evidence.read_text().startswith("PASS operation_ids="):
        raise SystemExit("actual canonical ABI evidence is absent")
    semantic=json.loads((DRAFTS/"semantic.json").read_text()); structural=json.loads((DRAFTS/"structural.json").read_text())
    semantic["operation_id_abi_check"]={"status":"PASS","evidence":str(abi_evidence.relative_to(ROOT)).replace("\\","/"),"sha256":sha_file(abi_evidence)}
    structural["operation_id_abi_check"]=semantic["operation_id_abi_check"]
    write_json(ROOT/"CANONICAL_SEMANTIC_HOLDOUT_V10_FREEZE.json",semantic)
    sem_rows=[]
    for c in semantic["cases"]:
        sem_rows.append({"case_id":c["case_id"],"framework":c["framework"],"source_path":c["source"]["path"],"source_sha256":c["source"]["sha256"],"source_line":c["source"]["line"],"action_family":c["action_family"],"scenario":c["deterministic_scenario"],"effect_semantics":c["declared_effect_semantics"],"profile_id":c["public_profile_id"],"operation_ids":"|".join(c["operation_ids"]),"executed":"NO"})
    write_csv(ROOT/"CANONICAL_SEMANTIC_HOLDOUT_V10_CASES.csv",sem_rows,list(sem_rows[0]))
    write_json(ROOT/"STRUCTURAL_SIZE_HOLDOUT_V10_FREEZE.json",structural)
    pair_rows=[]
    for p in structural["pairs"]:
        for av in p["arms"]:
            pair_rows.append({"pair_id":p["pair_id"],"stratum":p["stratum"],"arm_id":av["arm_id"],"profile_id":av["public_profile_id"],"private_agent_id":av["private_agent_id"],"actual_real_action_count":av["actual_real_action_count"],"operation_ids":"|".join(x["operation_id"] for x in av["private_actions"]),"executed":"NO"})
    write_csv(ROOT/"STRUCTURAL_SIZE_HOLDOUT_V10_PAIRS.csv",pair_rows,list(pair_rows[0]))
    semantic_order=sorted((c["case_id"] for c in semantic["cases"]),key=lambda x:sha_bytes((semantic["selection_seed"]+x).encode()))
    struct_seed=structural["pairs"][0]["structural_seed"]
    arm_order={p["pair_id"]:sorted((a["arm_id"] for a in p["arms"]),key=lambda x:sha_bytes((struct_seed+p["pair_id"]+x).encode())) for p in structural["pairs"]}
    write_json(ROOT/"V10_EXECUTION_ORDER.json",{"schema":"AgentTool.V10ExecutionOrder/1","selected_holdout_executed":False,"semantic_case_order":semantic_order,"structural_arm_order":arm_order})
    harness_files=[ROOT/"v10_holdout"/"harness.py",ROOT/"v10_holdout"/"operation_id_abi_check.go",ROOT/"tests"/"test_v10_holdout_harness.py",ROOT/"canonical_v9_1"/"profile.py",ROOT/"canonical_v9_1"/"projection.py"]
    frozen_inputs=[ROOT/"PUBLIC_PROFILE_V10.json",ROOT/"CANONICAL_SEMANTIC_HOLDOUT_V10_FREEZE.json",ROOT/"STRUCTURAL_SIZE_HOLDOUT_V10_FREEZE.json",ROOT/"V10_EXECUTION_ORDER.json",ROOT/"V10_DECISION_RULES.md",ROOT/"V10_LONG_HORIZON_RULES.md"]
    write_json(ROOT/"V10_HOLDOUT_HARNESS_FREEZE.json",{"schema":"AgentTool.V10HoldoutHarnessFreeze/1","selected_holdout_executed":False,"tests":"20 passed (harness plus V9.1 profile/projection fixtures)","sources":[{"path":str(p.relative_to(ROOT)).replace("\\","/"),"sha256":sha_file(p)} for p in harness_files],"frozen_inputs":[{"path":str(p.relative_to(ROOT)).replace("\\","/"),"sha256":sha_file(p)} for p in frozen_inputs],"execution_guard":"V10B authorization file required"})
    print("FINALIZED freeze manifests; no selected case executed")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("mode",choices=("prepare","finalize")); parser.add_argument("--abi-evidence",type=Path)
    args=parser.parse_args(); prepare() if args.mode=="prepare" else finalize(args.abi_evidence)

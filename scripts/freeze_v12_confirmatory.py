from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.freeze_v11a_confirmatory import rank, selected_action, workload_signature
from v11a_confirmatory.orchestrator import load_semantic_case, load_structural_arm, load_trajectory_case


PROFILE_ID = "V11_4-STRICT-ONLINE-H50-H3000-P10"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def selected_ids(path: str, field: str, identity: str) -> set[str]:
    return {str(item[identity]) for item in json.loads((ROOT / path).read_text())[field]}


def build_exclusions() -> dict[str, Any]:
    base = json.loads((ROOT / "V11A_MASTER_EXCLUSION_SET.json").read_text())
    s1 = json.loads((ROOT / "V11A_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json").read_text())["cases"]
    s2 = json.loads((ROOT / "V11A_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json").read_text())["cases"]
    s3 = json.loads((ROOT / "V11A_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json").read_text())["trajectories"]
    s4 = json.loads((ROOT / "V11A_EFFECT_CONTRACT_HOLDOUT_FREEZE.json").read_text())["cases"]
    structural = json.loads((ROOT / "V11A_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json").read_text())["pairs"]
    exact = set(base["source_site_exact"])
    reasons = list(base["source_exclusion_reasons"])
    for item in s1:
        source = item["source"]
        key = f'{item["framework"]}|{source["path"]}|{source["sha256"]}|{source["line"]}'
        exact.add(key)
        reasons.append({"kind": "SOURCE_SITE", "key": key, "reason": "V11A/V11B selected S1 holdout consumed"})
    signatures = set(base["workload_signatures"])
    for item in s2 + s4:
        signatures.add(workload_signature(item["framework"], "DYNAMIC_SEQUENCE", [item]))
    for item in s3:
        signatures.add(workload_signature(item["framework"], item["workflow"], item["actions"]))
    for pair in structural:
        for arm in pair["arms"]:
            signatures.add(workload_signature(arm["framework"], arm["workflow"], arm["actions"]))
    value = {
        "schema": "AgentTool.V12.MasterExclusionSet/1",
        "historical_base_sha256": sha256(ROOT / "V11A_MASTER_EXCLUSION_SET.json"),
        "historical_scope": "all historical exclusions plus every consumed V11A/V11B S1/S2/S3/S4 and structural workload",
        "source_file_wildcards": base["source_file_wildcards"],
        "source_site_exact": sorted(exact),
        "source_exclusion_reasons": reasons,
        "workload_signatures": sorted(signatures),
        "counts": {"whole_source_files": len(base["source_file_wildcards"]), "exact_source_sites": len(exact), "workload_signatures": len(signatures)},
        "selected_v12_cases_executed": 0,
    }
    value["aggregate_sha256"] = canonical_sha(value)
    write_json(ROOT / "V12_MASTER_EXCLUSION_SET.json", value)
    return value


def fresh_universes() -> dict[str, list[dict[str, Any]]]:
    mappings = {
        "s1": ("V11A_SOURCE_TOOL_UNIVERSE.json", "V11A_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json", "candidates", "cases", "candidate_id"),
        "s2": ("V11A_COMPOSITION_UNIVERSE.json", "V11A_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json", "candidates", "cases", "candidate_id"),
        "s3": ("V11A_CAUSAL_TRAJECTORY_UNIVERSE.json", "V11A_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json", "candidates", "trajectories", "candidate_id"),
        "s4": ("V11A_EFFECT_CONTRACT_UNIVERSE.json", "V11A_EFFECT_CONTRACT_HOLDOUT_FREEZE.json", "candidates", "cases", "candidate_id"),
        "structural": ("V11A_STRUCTURAL_PAIR_UNIVERSE.json", "V11A_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json", "candidates", "pairs", "candidate_pair_id"),
    }
    result = {}
    for key, (universe_file, selected_file, uf, sf, identity) in mappings.items():
        universe = json.loads((ROOT / universe_file).read_text())[uf]
        used = {item[identity] for item in json.loads((ROOT / selected_file).read_text())[sf]}
        result[key] = [item for item in universe if item[identity] not in used]
    if len(result["s1"]) < 20:
        raise RuntimeError("V12_FRESH_S1_POOL_INSUFFICIENT")
    freeze = {
        "schema": "AgentTool.V12.CandidateUniversesFreeze/1",
        "eligibility_seed_independent": True,
        "built_before_seed": True,
        "generator_sha256": sha256(Path(__file__).resolve()),
        "eligibility_rules": "unused candidates from the already-frozen seed-independent V11A universes after the complete V12 master exclusion update; no new adapter or framework revision",
        "frozen_system_inputs": {
            "development_evaluation": sha256(ROOT / "V12_DEVELOPMENT_EVALUATION_SUMMARY.json"),
            "runtime": sha256(ROOT / "v11_online" / "session.py"),
            "orchestrator": sha256(ROOT / "v11a_confirmatory" / "orchestrator.py"),
            "profile": sha256(ROOT / "PUBLIC_PROFILE_ONLINE_V11_4.json"),
        },
        "universes": result,
        "counts": {key: len(value) for key, value in result.items()},
        "hashes": {key: canonical_sha(value) for key, value in result.items()},
        "selected_v12_cases_executed": 0,
    }
    freeze["aggregate_sha256"] = canonical_sha(freeze)
    write_json(ROOT / "V12_CANDIDATE_UNIVERSES_FREEZE.json", freeze)
    return result


def derive_seeds(exclusions: dict[str, Any], universes: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    bound = {
        "v11b_postmortem": sha256(ROOT / "V11B_RESULT_TREE_MANIFEST.json"),
        "exclusions": sha256(ROOT / "V12_MASTER_EXCLUSION_SET.json"),
        "universes": sha256(ROOT / "V12_CANDIDATE_UNIVERSES_FREEZE.json"),
        "runtime": sha256(ROOT / "v11_online" / "session.py"),
        "profile": sha256(ROOT / "PUBLIC_PROFILE_ONLINE_V11_4.json"),
        "orchestrator": sha256(ROOT / "v11a_confirmatory" / "orchestrator.py"),
    }
    base = canonical_sha(bound)
    labels = {key: f"AgentTool-V12-{key}-v1" for key in ("s1", "s2", "s3", "s4", "structural", "order")}
    value = {"schema": "AgentTool.V12.SelectionSeeds/1", "bound_inputs": bound, "base_seed": base, "labels": labels, "seeds": {key: hashlib.sha256(f"{base}|{label}".encode()).hexdigest() for key, label in labels.items()}, "seed_search": False}
    write_json(ROOT / "V12_SELECTION_SEEDS.json", value)
    return value


def select_s1(values, seed):
    ordered = sorted(values, key=lambda item: rank(seed, item["candidate_id"]))
    selected, per_file = [], Counter()
    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        for item in [x for x in ordered if x["framework"] == framework]:
            key = (framework, item["source_path"])
            if per_file[key] >= 2: continue
            selected.append(item); per_file[key] += 1
            if sum(x["framework"] == framework for x in selected) >= min(10, sum(y["framework"] == framework for y in values)): break
    for item in ordered:
        key = (item["framework"], item["source_path"])
        if item in selected or per_file[key] >= 2: continue
        selected.append(item); per_file[key] += 1
        if len(selected) == 20: break
    result=[]
    for i,item in enumerate(sorted(selected,key=lambda x:rank(seed,x["candidate_id"])),1):
        case=selected_action(item,f"V12-S1-{i:03d}","S1_SOURCE_TOOL")
        case.update(candidate_id=item["candidate_id"],adapter_id=item["adapter_id"],source={"path":item["source_path"],"sha256":item["source_sha256"],"line":item["source_line"],"detail":item["source_detail"]},frozen_corpus_disposition="MEDIATED",effect_contract_origin="SYNTHETIC_CONFIRMATORY_CONTRACT",level="LEVEL_A_ACTION_BOUNDARY")
        result.append(case)
    return result


def select_s2(values, seed):
    chosen=[]
    for family in ("OPENAI_AGENT_AS_TOOL","OPENAI_HANDOFF","MICROSOFT_AGENT_AS_TOOL"):
        chosen += sorted([x for x in values if x["composition_family"]==family],key=lambda x:rank(seed,x["candidate_id"]))[:4]
    result=[]
    for i,item in enumerate(sorted(chosen,key=lambda x:rank(seed,x["candidate_id"])),1):
        case=selected_action(item,f"V12-S2-{i:03d}","S2_COMPOSITION")
        case.update(candidate_id=item["candidate_id"],composition_family=item["composition_family"],effect_contract_origin="SYNTHETIC_CONFIRMATORY_CONTRACT",level="LEVEL_A_ACTION_BOUNDARY")
        result.append(case)
    return result


def select_s3(values, seed):
    chosen=[]
    for framework,depth in (("OpenAI Agents SDK",50),("Microsoft Agent Framework",30)):
        chosen.append(min([x for x in values if x["framework"]==framework and x["depth"]==depth],key=lambda x:rank(seed,x["candidate_id"])))
    for framework in ("OpenAI Agents SDK","Microsoft Agent Framework"):
        for item in sorted([x for x in values if x["framework"]==framework],key=lambda x:rank(seed,x["candidate_id"])):
            if item in chosen: continue
            chosen.append(item)
            if sum(x["framework"]==framework for x in chosen)==6: break
    result=[]
    for i,item in enumerate(sorted(chosen,key=lambda x:rank(seed,x["candidate_id"])),1):
        actions=copy.deepcopy(item["actions"])
        for j,action in enumerate(actions,1):
            action.update(case_id=f"V12-S3-{i:03d}-A{j:02d}",operation_id=("op"+f"V12S3{i:03d}A{j:02d}")[:32],manifest_kind="S3_CAUSAL_ACTION",selected_case_executed=False)
        result.append({"manifest_kind":"S3_CAUSAL_TRAJECTORY","trajectory_id":f"V12-S3-{i:03d}","candidate_id":item["candidate_id"],"framework":item["framework"],"trajectory_family":item["trajectory_family"],"workflow":item["workflow"],"depth":item["depth"],"actions":actions,"public_profile_id":PROFILE_ID,"selected_case_executed":False,"level":"LEVEL_A_ACTION_BOUNDARY"})
    return result


def select_s4(values, seed):
    result=[]
    chosen=sorted(values,key=lambda x:rank(seed,x["candidate_id"]))
    for i,item in enumerate(chosen,1):
        case=selected_action(item,f"V12-S4-{i:03d}","S4_EFFECT_CONTRACT")
        case.update(candidate_id=item["candidate_id"],effect_contract_origin="SYNTHETIC_CONFIRMATORY_CONTRACT",level="LEVEL_A_CANONICAL_EFFECT_CONTRACT")
        result.append(case)
    return result


def select_structural(values, seed):
    grouped=defaultdict(list)
    for item in values: grouped[item["stratum"]].append(item)
    def n(s): return int(re.match(r"P(\d+)_",s).group(1))
    result=[]
    for i,stratum in enumerate(sorted(grouped,key=n),1):
        item=min(grouped[stratum],key=lambda x:rank(seed,x["candidate_pair_id"]))
        arms=copy.deepcopy(item["arms"])
        for ai,arm in enumerate(arms):
            arm["arm_id"]=f"V12-P{i:02d}-{'A' if ai==0 else 'B'}"; arm["selected_arm_executed"]=False
            for j,action in enumerate(arm["actions"],1):
                action.update(case_id=f"{arm['arm_id']}-A{j:02d}",operation_id=("op"+arm["arm_id"].replace("-","")+f"A{j:02d}")[:32],manifest_kind="STRUCTURAL_ACTION",selected_case_executed=False)
        result.append({"pair_id":f"V12-P{i:02d}","candidate_pair_id":item["candidate_pair_id"],"stratum":stratum,"arms":arms,"public_profile_id":PROFILE_ID,"selected_pair_executed":False})
    return result


def main() -> None:
    if (ROOT / "results_v12_confirmatory").exists(): raise RuntimeError("selected V12 result root must not exist")
    dev=json.loads((ROOT/"V12_DEVELOPMENT_EVALUATION_SUMMARY.json").read_text())
    if dev.get("ready_for_holdout_freeze") is not True: raise RuntimeError("development gates did not pass")
    exclusions=build_exclusions(); universes=fresh_universes(); seeds=derive_seeds(exclusions,universes)
    s1=select_s1(universes["s1"],seeds["seeds"]["s1"]); s2=select_s2(universes["s2"],seeds["seeds"]["s2"]); s3=select_s3(universes["s3"],seeds["seeds"]["s3"]); s4=select_s4(universes["s4"],seeds["seeds"]["s4"]); structural=select_structural(universes["structural"],seeds["seeds"]["structural"])
    outputs={
        "V12_SOURCE_SEMANTIC_HOLDOUT_FREEZE.json":{"schema":"AgentTool.V12.SourceSemanticHoldoutFreeze/1","cases":s1,"selected_holdout_executed":False},
        "V12_COMPOSITION_SEMANTIC_HOLDOUT_FREEZE.json":{"schema":"AgentTool.V12.CompositionSemanticHoldoutFreeze/1","cases":s2,"microsoft_handoff":"NATIVE_MECHANISM_ABSENT","selected_holdout_executed":False},
        "V12_CAUSAL_TRAJECTORY_HOLDOUT_FREEZE.json":{"schema":"AgentTool.V12.CausalTrajectoryHoldoutFreeze/1","trajectories":s3,"selected_holdout_executed":False},
        "V12_EFFECT_CONTRACT_HOLDOUT_FREEZE.json":{"schema":"AgentTool.V12.EffectContractHoldoutFreeze/1","cases":s4,"selected_holdout_executed":False},
        "V12_STRUCTURAL_SIZE_HOLDOUT_FREEZE.json":{"schema":"AgentTool.V12.StructuralSizeHoldoutFreeze/1","pairs":structural,"public_profile_id":PROFILE_ID,"selected_holdout_executed":False},
    }
    for name,value in outputs.items(): write_json(ROOT/name,value)
    for item in s1+s2+s4: load_semantic_case(item)
    for item in s3: load_trajectory_case(item)
    for pair in structural:
        for arm in pair["arms"]: load_structural_arm(arm)
    order_seed=seeds["seeds"]["order"]
    sem=[x["case_id"] for x in s1+s2+s4]; traj=[x["trajectory_id"] for x in s3]; arms=[a["arm_id"] for p in structural for a in p["arms"]]
    order={"schema":"AgentTool.V12.ExecutionOrder/1","semantic_case_order":sorted(sem,key=lambda x:rank(order_seed,x)),"causal_trajectory_order":sorted(traj,key=lambda x:rank(order_seed,x)),"structural_arm_order":sorted(arms,key=lambda x:rank(order_seed,x)),"selected_v12_cases_executed":0}
    write_json(ROOT/"V12_EXECUTION_ORDER.json",order)
    units=[]
    index=0
    for family,phase,ids in (("SEMANTIC","1_SEMANTIC",order["semantic_case_order"]),("TRAJECTORY","2_CAUSAL_TRAJECTORY",order["causal_trajectory_order"])):
        for identity in ids:
            for role in ("NATIVE","CANONICAL"):
                index+=1; units.append({"global_execution_index":index,"unit_id":f"V12-U{index:03d}","phase":phase,"family":"S3" if family=="TRAJECTORY" else next(k for k,values in (("S1",s1),("S2",s2),("S4",s4)) if identity in {v["case_id"] for v in values}),"role":role,"target_id":identity,"retry_allowed":False})
    for identity in order["structural_arm_order"]:
        index+=1; units.append({"global_execution_index":index,"unit_id":f"V12-U{index:03d}","phase":"3_STRUCTURAL","family":next(p["pair_id"] for p in structural if identity in {a["arm_id"] for a in p["arms"]}),"role":"STRUCTURAL_ARM","target_id":identity,"retry_allowed":False})
    if index != 134: raise AssertionError(index)
    write_json(ROOT/"V12_EXECUTION_PLAN.json",{"schema":"AgentTool.V12.ExecutionPlan/1","unit_count":134,"native_units":53,"canonical_units":81,"units":units,"selected_v12_cases_executed":0})
    print(f"V12_S1_POOL={len(universes['s1'])} SELECTED={len(s1)} S2={len(s2)} S3={len(s3)} S4={len(s4)} STRUCTURAL={len(structural)} UNITS={index}")


if __name__ == "__main__": main()

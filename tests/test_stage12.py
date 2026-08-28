from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from stage12_final_p0.live_core import LiveConfig, StepResult, assert_host_trace, run_live, serialize_frame
from stage12_final_p0.workload import PublicTask, load_workload


def _step(raw: int, ready: bool = False):
    async def run() -> StepResult: return StepResult(raw, False, ready)
    return run


async def _approval() -> None: return None


def _commit(): return {"effect_type":"synthetic_effect","task_id":"task"}


def test_actual_fixed_serialization_has_exact_length():
    assert len(serialize_frame(117,"FIXED",1024,(256,512,1024)))==1024
    assert len(serialize_frame(117,"BUCKET",1024,(256,512,1024)))==256
    with pytest.raises(OverflowError): serialize_frame(2048,"FIXED",1024,(256,512,1024))


def test_m3_live_shapes_different_native_paths_identically():
    cfg=LiveConfig(5,1.0,1024,2.0,"FIXED")
    short=asyncio.run(run_live(variant="M3",config=cfg,real_steps=[_step(300,True)],approval_work=_approval,commit=_commit,seed=1))
    long=asyncio.run(run_live(variant="M3",config=cfg,real_steps=[_step(600),_step(400,True)],approval_work=_approval,commit=_commit,seed=2))
    projection=lambda result:[(e["operation_class"],e["serialized_bytes"]) for e in result["host_visible_trace"]]
    assert projection(short)==projection(long)
    assert short["effect_count"]==long["effect_count"]==1
    assert short["dummy_external_effects"]==long["dummy_external_effects"]==0


def test_m2_retains_size_leak_but_fixed_m3_removes_it():
    cfg=LiveConfig(5,1,1024,1,"FIXED")
    a=asyncio.run(run_live(variant="M2",config=cfg,real_steps=[_step(200,True)],approval_work=_approval,commit=_commit,seed=3))
    b=asyncio.run(run_live(variant="M2",config=cfg,real_steps=[_step(800),_step(300,True)],approval_work=_approval,commit=_commit,seed=4))
    assert [e["serialized_bytes"] for e in a["host_visible_trace"]] != [e["serialized_bytes"] for e in b["host_visible_trace"]]


def test_failure_before_commit_is_fail_closed():
    effects=[]
    async def broken(): raise TimeoutError("internal service unavailable")
    with pytest.raises(TimeoutError):
        asyncio.run(run_live(variant="M3",config=LiveConfig(3,1,1024,1,"FIXED"),real_steps=[broken],
                             approval_work=_approval,commit=lambda:effects.append("effect"),seed=5))
    assert effects==[]


def test_host_error_and_trace_secrecy():
    trace=[{"operation_class":"MEDIATION_SLOT","serialized_bytes":1024}]
    assert_host_trace(trace)
    for secret in ("private_state","permission_exists","provenance_exists","logical_id","is_dummy"):
        with pytest.raises(AssertionError): assert_host_trace([{secret:"CONTACT_17"}])


def test_workload_has_40_public_derived_tasks():
    root=Path(__file__).resolve().parents[1]
    tasks=load_workload(root/"PUBLIC_DERIVED_WORKLOAD.csv")
    assert len(tasks)==40
    assert {task.source for task in tasks}=={"tau2-bench","AgentDojo"}
    assert all(task.private_configurations==4 for task in tasks)


def test_ground_truth_is_serialized_separately_from_host_trace():
    root=Path(__file__).resolve().parents[1]
    host=json.loads((root/"results_stage12"/"runtime2_host.jsonl").read_text(encoding="utf-8").splitlines()[0])
    encoded=json.dumps(host["host_visible_trace"],sort_keys=True)
    assert "AUTHORIZATION" not in encoded
    assert "branch" not in encoded
    assert "private_state" not in encoded


def test_live_outputs_preserve_all_effect_invariants():
    root=Path(__file__).resolve().parents[1]
    for name in ("runtime1_host.jsonl","runtime2_host.jsonl"):
        for line in (root/"results_stage12"/name).read_text(encoding="utf-8").splitlines():
            row=json.loads(line)
            assert row["effect_count"]==1
            assert row["dummy_external_effects"]==0
            assert row["authorization_preserved"] is True


def test_selected_horizon_has_no_secret_dependent_overflow():
    root=Path(__file__).resolve().parents[1]
    rows=(root/"results_stage12"/"horizon_summary.csv").read_text(encoding="utf-8").splitlines()
    selected=next(row for row in rows if row.startswith("5,"))
    assert ",1.0,0.0,0.5," in selected

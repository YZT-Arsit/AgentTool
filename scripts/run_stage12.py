from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from stage12_final_p0.attacks import run_attacks
from stage12_final_p0.summarize import summarize
from stage12_final_p0.supporting import run_supporting
from stage12_final_p0.workload import build_workload


def main() -> None:
    results=ROOT/"results_stage12"; results.mkdir(exist_ok=True)
    workload=ROOT/"PUBLIC_DERIVED_WORKLOAD.csv"; build_workload(workload)
    commands=[
        (ROOT/".venv-stage9"/"Scripts"/"python.exe","stage12_final_p0.runtime1_live","runtime1"),
        (ROOT/".venv-stage10"/"Scripts"/"python.exe","stage12_final_p0.runtime2_live","runtime2"),
    ]
    for python,module,stem in commands:
        env=dict(os.environ)
        if stem=="runtime1": env["PYTHONPATH"]=os.pathsep.join([str(ROOT/"external_stage9"/"agent-framework"/"python"/"packages"/"core"),str(ROOT)])
        subprocess.run([str(python),"-m",module,"--workload",str(workload),"--output",str(results/f"{stem}_host.jsonl"),
            "--truth-output",str(results/f"{stem}_truth.csv"),"--profile-output",str(results/f"{stem}_profile.json")],cwd=ROOT,env=env,check=True)
    run_supporting(workload,results)
    run_attacks([results/"runtime1_host.jsonl",results/"runtime2_host.jsonl"],
                [results/"runtime1_truth.csv",results/"runtime2_truth.csv"],results/"attack_results.csv",results/"symbolic_equality.csv")
    summary=summarize(results)
    print(f"STAGE-12 DECISION:\n{summary['stage12_decision']}")


if __name__=="__main__": main()


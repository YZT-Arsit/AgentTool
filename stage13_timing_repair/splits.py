from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from stage12_final_p0.workload import PublicTask, load_workload


def frozen_split(tasks: list[PublicTask]) -> dict[str, str]:
    ranked=sorted(tasks,key=lambda task:hashlib.sha256(("stage13-split-v1:"+task.workload_id).encode()).hexdigest())
    return {task.workload_id:("CALIBRATION" if index<12 else "DEVELOPMENT" if index<24 else "FINAL_TEST")
            for index,task in enumerate(ranked)}


def write_split(workload: Path, output: Path) -> dict[str, str]:
    tasks=load_workload(workload); split=frozen_split(tasks)
    with output.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=["task_id","source","domain","split"]);writer.writeheader()
        for task in tasks: writer.writerow({"task_id":task.workload_id,"source":task.source,"domain":task.domain,"split":split[task.workload_id]})
    return split


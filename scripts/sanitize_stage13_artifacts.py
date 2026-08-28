from __future__ import annotations

import csv
import json
from pathlib import Path


PRIVATE_KEYS=("proposal_queue_time_ns","done_time_ns","worker_done_by_epoch_end",
              "authorization_preserved","effect_equivalent","state_preserved")


def read_jsonl(path:Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_jsonl(path:Path,rows):
    path.write_text("".join(json.dumps(row,sort_keys=True)+"\n" for row in rows),encoding="utf-8")


def sanitize(stem:str,root:Path)->None:
    host_path=root/f"{stem}_final_host.jsonl";private_path=root/f"{stem}_private_instrumentation.jsonl"
    hosts=read_jsonl(host_path);private={row["run_id"]:row for row in read_jsonl(private_path)};mapping={}
    new_private=[]
    for index,row in enumerate(hosts):
        old=row["run_id"];new=f"{stem}-final-{index:04d}";mapping[old]=new;row["run_id"]=new
        trusted=private[old]; trusted["run_id"]=new
        if "events" in trusted: trusted["private_instrumentation"]=trusted.pop("events")
        for key in PRIVATE_KEYS:
            if key in row: trusted[key]=row.pop(key)
        new_private.append(trusted)
    write_jsonl(host_path,hosts);write_jsonl(private_path,new_private)
    truth_path=root/f"{stem}_truth.csv"
    with truth_path.open(encoding="utf-8",newline="") as handle:truth=list(csv.DictReader(handle))
    for row in truth:row["run_id"]=mapping[row["run_id"]]
    with truth_path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(truth[0]));writer.writeheader();writer.writerows(truth)

    dev_host_path=root/f"{stem}_development.jsonl";dev_private_path=root/f"{stem}_development_private.jsonl"
    dev_hosts=read_jsonl(dev_host_path);dev_private={row["run_id"]:row for row in read_jsonl(dev_private_path)}
    clean=[]
    for row in dev_hosts:
        trusted=dev_private[row["run_id"]]
        if "events" in trusted:trusted["private_instrumentation"]=trusted.pop("events")
        for key in PRIVATE_KEYS:
            if key in row:trusted[key]=row.pop(key)
        clean.append(trusted)
    write_jsonl(dev_host_path,dev_hosts);write_jsonl(dev_private_path,clean)


if __name__=="__main__":
    root=Path("results_stage13")
    for stem in ("runtime1","runtime2"):sanitize(stem,root)

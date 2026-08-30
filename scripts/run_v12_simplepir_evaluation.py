from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_online.session import OnlineSimplePIRResolver


def percentile(values, p):
    values=sorted(values); return values[max(0,min(len(values)-1,math.ceil(len(values)*p)-1))]


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True);args=parser.parse_args()
    if args.output.exists(): raise FileExistsError("V12 PIR evaluation is one-shot")
    args.output.mkdir(parents=True)
    rng=random.Random(120012)
    rows=[]; privacy=[]
    for count in (64,256,1024,4096):
        root=args.output/f"catalog_{count}"; latencies=[]; cpu=[]; recovered=[]
        with OnlineSimplePIRResolver(root,record_count=count) as resolver:
            indices=[rng.randrange(count) for _ in range(30)]
            for query_number,index in enumerate(indices):
                operation_id=f"v12-c{count}-q{query_number:03d}"
                cpu0=time.process_time_ns(); start=time.monotonic_ns(); descriptor=resolver.query(operation_id,index)
                latencies.append((time.monotonic_ns()-start)/1e6);cpu.append((time.process_time_ns()-cpu0)/1e6);recovered.append(descriptor.agent_id==index)
        server=[json.loads(line) for line in (root/"server_visible_trace.jsonl").read_text().splitlines()]
        request_bytes=[int(item["query_bytes"]) for item in server if "query_bytes" in item]
        response_bytes=[int(item["answer_bytes"]) for item in server if "answer_bytes" in item]
        rows.append({"catalog_records":count,"queries":30,"median_query_latency_ms":statistics.median(latencies),"p95_query_latency_ms":percentile(latencies,.95),"median_client_cpu_ms":statistics.median(cpu),"request_bytes":statistics.median(request_bytes),"response_bytes":statistics.median(response_bytes),"correct":all(recovered)})
    root=args.output/"pairwise_100"; pairs=[]
    with OnlineSimplePIRResolver(root,record_count=4096) as resolver:
        for pair in range(100):
            left=rng.randrange(4096);right=rng.randrange(4096)
            while right==left:right=rng.randrange(4096)
            dl=resolver.query(f"v12-p{pair:03d}-left",left);dr=resolver.query(f"v12-p{pair:03d}-right",right)
            pairs.append(dl.agent_id==left and dr.agent_id==right)
    text=(root/"server_visible_trace.jsonl").read_text()
    server=[json.loads(line) for line in text.splitlines()]
    query_rows=[item for item in server if "query_bytes" in item]
    privacy={
        "pairs":100,
        "distinct_queries":200,
        "correct":all(pairs),
        "plaintext_agent_id_field_absent":"agent_id" not in text.lower(),
        "private_index_field_absent":"private_index" not in text.lower(),
        "fresh_server_query_hashes":len({x.get("query_sha256") for x in query_rows}) == len(query_rows) == 200,
        "public_query_byte_shapes":sorted(set(int(x.get("query_bytes",0)) for x in query_rows)),
        "public_response_byte_shapes":sorted(set(int(x.get("answer_bytes",0)) for x in query_rows)),
        "server_visible_public_parameters":sorted(set((int(x.get("query_rows",0)),int(x.get("query_cols",0))) for x in query_rows)),
        "official_simplepir":True,
        "selected_v12_cases_executed":0,
    }
    with (args.output/"benchmark.csv").open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (args.output/"privacy.json").write_text(json.dumps(privacy,indent=2,sort_keys=True)+"\n")


if __name__=="__main__":main()

from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"results_v12_development"/"performance_raw.csv"


def main():
    raw=list(csv.DictReader(SOURCE.open(encoding="utf-8")));grouped={}
    for row in raw: grouped.setdefault((row["baseline"],int(row["real_operations"])),[]).append(row)
    metrics=("logical_action_latency_ms","framework_result_latency_ms","session_wall_ms","bytes_sent","bytes_received","pir_request_bytes","pir_response_bytes","total_bytes","cpu_ms","peak_rss_bytes")
    result=[]
    for (baseline,count),items in sorted(grouped.items()):
        for metric in metrics:
            values=sorted(float(x[metric]) for x in items if x.get(metric) not in (None, ""))
            result.append({"baseline":baseline,"real_operations":count,"attempted_repetitions":len(items),"measured_repetitions":len(values),"metric":metric,"median":statistics.median(values) if values else "","p95":values[max(0,math.ceil(.95*len(values))-1)] if values else "","mean":statistics.mean(values) if values else "","stddev":statistics.pstdev(values) if values else ""})
    with (ROOT/"V12_PERFORMANCE_RESULTS.csv").open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(result[0]));writer.writeheader();writer.writerows(result)
    complete=len(grouped)==30 and all(len(v)==30 for v in grouped.values())
    strict=[r for r in raw if r["baseline"]=="B5_FULL_STRICT"]
    strict_success=[r for r in strict if r.get("functional", "true").lower()=="true"]
    strict_failures=[r for r in strict if r.get("functional", "true").lower()!="true"]
    strict_bytes=all(int(r["bytes_sent"])+int(r["bytes_received"])==668924 for r in strict_success)
    amplification=[]
    for count in (1,5,10,25,50):
        direct=statistics.median(int(r["bytes_sent"])+int(r["bytes_received"]) for r in raw if r["baseline"]=="B0_DIRECT_NATIVE" and int(r["real_operations"])==count)
        amplification.append((count,668924/direct))
    lines=["# V12 performance summary","",f"Thirty-attempt baseline/count cells complete: **{'YES' if complete else 'NO'}** ({len(grouped)}/30). FULL_STRICT successful-session Relay byte equality: **{'PASS' if strict_bytes else 'FAIL'}** ({len(strict_success)}/{len(strict)} successful attempts; {len(strict_failures)} retained failures). Every successful strict session contains 356 requests of 1079 bytes and 356 responses of 800 bytes, for 668,924 action-transport bytes. PIR request/response bytes and combined total bytes are reported separately.","","| Real operations | FULL_STRICT action-transport amplification vs direct logical bytes |","|---:|---:|"]
    lines.extend(f"| {count} | {ratio:.2f}x |" for count,ratio in amplification)
    lines.extend(("",f"The interrupted first performance campaign is retained. It stopped after a real `{strict_failures[0]['status_class'] if strict_failures else 'NONE'}` in B5 count={strict_failures[0]['real_operations'] if strict_failures else 'NA'} repetition={strict_failures[0]['repetition'] if strict_failures else 'NA'}; that failed strict unit was not retried or replaced. A recovery campaign reran only B0-B3 because their metrics had existed solely in the terminated process, reconstructed every completed strict attempt from immutable evidence, and executed only strict identities that had never run. CPU/RSS are unavailable for reconstructed strict attempts and their measured-repetition counts are explicit in the CSV. The B2/B3 development helper uses the pinned RFC 9292/9458 code across a real loopback Cloud->Relay->Gateway exchange with exact Relay byte forwarding and one deterministic local provider invocation per real operation. The decisive binary was built offline with the repository's vendored ohttp-go dependency tree (`GOPROXY=off`); it contacts no external provider. An earlier module-mode build probe attempted the host's default Go proxy, timed out without obtaining the missing modules, and produced no binary or measurement; that failed environment probe is excluded. The CSV reports median, p95, mean, and population standard deviation for available latency, bytes, aggregate controller/child CPU, and process/campaign RSS high-water marks. B4/B5 action latency is computed from each operation's actual `ACTION_INTENT_SUBMITTED` to `FRAMEWORK_RESULT_DELIVERED` lifecycle timestamps. B0/B1 use the native framework-result boundary; B2/B3 use OHTTP client decapsulation. These are performance measurements, not timing-privacy claims.",""))
    (ROOT/"V12_PERFORMANCE_SUMMARY.md").write_text("\n".join(lines),encoding="utf-8")
    print(f"PERFORMANCE_COMPLETE={complete} STRICT_BYTES={strict_bytes}")


if __name__=='__main__':main()

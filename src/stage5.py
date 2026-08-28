from __future__ import annotations

import hashlib,math,random,time
from collections import Counter,defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean,pstdev

from .experiment import svg_bar,write_csv
from .path_oram import PathORAM
from .stage2 import binary_eval,percentile,perm_binary,svg_scatter
from .stage4 import ArchitectureStorage,IndependentEpisode

ARCHS=("MODULAR-ORAM","NAIVE-FIXED","CANONICAL-MODULAR","UNIFIED-FIXED","UNIFIED-PACKED","RANDOMIZED-PARTITION","HYBRID-P","HYBRID-PH","SCAN-PERMISSION","SCAN-HISTORY","SCAN-BOTH")
PRIVACY={a:("leak" if a=="MODULAR-ORAM" else ("not_implemented" if a=="RANDOMIZED-PARTITION" else "pass")) for a in ARCHS}
REGIMES={
 "S":{"data":256,"perm":128,"hist":256},
 "M":{"data":8192,"perm":1024,"hist":4096},
 "L":{"data":65536,"perm":16384,"hist":131072},
 "H":{"data":65536,"perm":512,"hist":8192},
}
BASE_REC={"data":4096,"perm":128,"hist":256};Z=4;PACK_BLOCK=4096
PROFILES={"LOCAL":{"rtt_ms":.005,"mbps":10000},"DATACENTER":{"rtt_ms":.2,"mbps":2000},"REMOTE":{"rtt_ms":5.0,"mbps":200}}

def pow2(n):return 1 if n<=1 else 1<<(n-1).bit_length()
def tree(n,block):
    h=max(1,math.ceil(math.log2(max(2,n))));nodes=(1<<(h+1))-1
    return {"height":h,"path_blocks":2*(h+1)*Z,"path_bytes":2*(h+1)*Z*block,"tree_bytes":nodes*Z*block,"position_bytes":n*4,"nodes":nodes}
def packed_layout(counts,rec):
    factors={k:max(1,PACK_BLOCK//(rec[k]+16)) for k in counts};pages={k:math.ceil(counts[k]/factors[k]) for k in counts}
    return factors,pages,sum(pages.values())

class RandomizedPartitionORAM:
    """Functional randomized-remap partition abstraction, not Partition ORAM.

    A private map assigns every logical slot to a uniformly shuffled physical
    partition/slot. Each access always reads the old Path-ORAM slot and writes a
    newly selected free slot, then updates the private map. This omits the cache
    and background eviction proof machinery of formal Partition ORAM.
    """
    def __init__(self,n,seed,partitions=8,z=4):
        self.n=n;self.p=partitions;self.rng=random.Random(seed);self.capacity=math.ceil(n/partitions*1.25)+2
        self.orams=[PathORAM(self.capacity,seed+i*1009,z,math.ceil(math.log2(self.capacity))) for i in range(partitions)]
        slots=[(p,s) for p in range(partitions) for s in range(self.capacity)];self.rng.shuffle(slots);self.mapping={i:slots[i] for i in range(n)};used=set(self.mapping.values());self.free={p:{s for s in range(self.capacity) if (p,s) not in used} for p in range(partitions)};self.values={i:f"value_{i}" for i in range(n)}
    def access(self,i,op="read",value=None):
        oldp,olds=self.mapping[i];prior=self.values[i];_,a=self.orams[oldp].access(olds,"read")
        self.free[oldp].add(olds);available=[p for p in range(self.p) if self.free[p]];newp=self.rng.choice(available);news=self.rng.choice(tuple(self.free[newp]));self.free[newp].remove(news)
        if op=="write":self.values[i]=value
        _,b=self.orams[newp].access(news,"write",self.values[i]);self.mapping[i]=(newp,news)
        return prior,[{"store":f"PARTITION_{oldp}","operation":"path_read",**a},{"store":f"PARTITION_{newp}","operation":"path_write",**b}]
    def assert_invariants(self):
        if len(set(self.mapping.values()))!=self.n:raise AssertionError("duplicate partition slot")
        for p,s in self.mapping.values():
            if s in self.free[p]:raise AssertionError("mapped slot marked free")
        for o in self.orams:o.assert_invariants()

class Stage5Mediator:
    stores={"PRIVATE_DATA_DB":256,"PERMISSION_DB":128,"DISCLOSURE_LOG":256}
    def __init__(self,arch,seed):
        self.arch=arch;self.seed=seed
        if arch=="RANDOMIZED-PARTITION":self.part=RandomizedPartitionORAM(sum(self.stores.values()),seed);self.offset={"PRIVATE_DATA_DB":0,"PERMISSION_DB":256,"DISCLOSURE_LOG":384}
        else:
            ext=dict(self.stores)
            if arch=="HYBRID-P":ext.pop("PERMISSION_DB")
            if arch=="HYBRID-PH":ext={"PRIVATE_DATA_DB":256}
            unified=arch in ("UNIFIED-FIXED","UNIFIED-PACKED")
            self.storage=ArchitectureStorage(ext,"UNIFIED-ORAM" if unified else "MODULAR-ORAM",seed)
    def _a(self,store,key,op,trace):
        if self.arch=="RANDOMIZED-PARTITION":
            logical=self.offset[store]+int.from_bytes(hashlib.sha256(key.encode()).digest()[:4],"big")%self.stores[store];_,ev=self.part.access(logical,op,f"update:{key}");trace.extend(ev)
        else:self.storage.access(store,key,op,"stage5_semantic_access",store)
    def execute(self,e):
        start=time.perf_counter_ns();trace=[];dummy=0
        fixed=self.arch in ("NAIVE-FIXED","CANONICAL-MODULAR","HYBRID-P","SCAN-PERMISSION","SCAN-HISTORY","SCAN-BOTH")
        if self.arch=="HYBRID-PH":self._a("PRIVATE_DATA_DB",f"DATA_{e.entity}" if not e.hidden_state else "DUMMY_DATA","read",trace);dummy+=e.hidden_state
        elif self.arch.startswith("SCAN"):
            self._a("PRIVATE_DATA_DB",f"DATA_{e.entity}" if not e.hidden_state else "DUMMY_DATA","read",trace);dummy+=e.hidden_state
            if self.arch not in ("SCAN-PERMISSION","SCAN-BOTH"):self._a("PERMISSION_DB",f"PERM_{e.entity}","read",trace)
            else:trace.append({"store":"PERMISSION_SCAN","operation":"fixed_scan","order":len(trace)})
            if self.arch in ("SCAN-HISTORY","SCAN-BOTH"):trace.append({"store":"HISTORY_SCAN","operation":"fixed_scan_update","order":len(trace)})
            else:
                self._a("DISCLOSURE_LOG",f"PRIOR_{e.entity}" if e.hidden_state else "DUMMY_PRIOR","read",trace);dummy+=not e.hidden_state;self._a("DISCLOSURE_LOG",f"WRITE_{e.entity}","write",trace)
        elif fixed:
            self._a("PRIVATE_DATA_DB",f"DATA_{e.entity}" if not e.hidden_state else "DUMMY_DATA","read",trace);dummy+=e.hidden_state
            self._a("DISCLOSURE_LOG",f"PRIOR_{e.entity}" if e.hidden_state else "DUMMY_PRIOR","read",trace);dummy+=not e.hidden_state
            if self.arch not in ("HYBRID-P",):self._a("PERMISSION_DB",f"PERM_{e.entity}","read",trace)
            self._a("DISCLOSURE_LOG",f"WRITE_{e.entity}","write",trace)
        else:
            self._a("DISCLOSURE_LOG" if e.hidden_state else "PRIVATE_DATA_DB",f"SOURCE_{e.entity}","read",trace);self._a("PERMISSION_DB",f"PERM_{e.entity}","read",trace);self._a("DISCLOSURE_LOG",f"WRITE_{e.entity}","write",trace)
        if hasattr(self,"storage"):
            h,_=self.storage.reset();trace=[*trace,*h] if self.arch.startswith("SCAN") else h
        result={"authorized":e.authorized,"private_value":f"synthetic_private_value_{e.entity}" if e.authorized else None,"disclosure_updated":True,"tool_outcome":"sent" if e.authorized else "denied"}
        return result,trace,(time.perf_counter_ns()-start)/1000,dummy

def privacy_features(t):
    stores=[x["store"] for x in t];events=[f"{x['store']}_{x['operation']}" for x in t]
    return [f"len={len(t)}"]+[f"h:{s}={stores.count(s)}" for s in sorted(set(stores))]+[f"p:{i}:{e}" for i,e in enumerate(events)]+[f"ng:{a}>{b}" for a,b in zip(events,events[1:])]

def architecture_cost(arch,counts,rec,mix=None):
    mix=mix or {"data":1,"perm":1,"hist_read":1,"hist_write":1};blocks={k:pow2(v) for k,v in rec.items()};trees={k:tree(counts[k],blocks[k]) for k in counts};logical_payload=sum(counts[k]*rec[k] for k in counts)
    paths=0;bucket_blocks=0;bytes_=0;rounds=0;server=0;pos=0;trusted=0;dummy=0;logical=0
    tree_desc=";".join(f"{k}:{v['height']}" for k,v in trees.items());block_desc=";".join(f"{k}:{blocks[k]}" for k in counts);n_desc=";".join(f"{k}:{counts[k]}" for k in counts)
    for t in trees.values():server+=t["tree_bytes"];pos+=t["position_bytes"]
    def add(k,num=1):
        nonlocal paths,bucket_blocks,bytes_,logical;paths+=num;logical+=num;bucket_blocks+=trees[k]["path_blocks"]*num;bytes_+=trees[k]["path_bytes"]*num
    if arch=="MODULAR-ORAM":
        # Equal mixture: one of data/history source + permission + history write.
        logical=3;paths=3;bucket_blocks=.5*trees["data"]["path_blocks"]+trees["perm"]["path_blocks"]+1.5*trees["hist"]["path_blocks"];bytes_=.5*trees["data"]["path_bytes"]+trees["perm"]["path_bytes"]+1.5*trees["hist"]["path_bytes"];rounds=3;dummy=0
    elif arch in ("NAIVE-FIXED","CANONICAL-MODULAR"):
        add("data");add("perm");add("hist",2);rounds=3;dummy=.25
    elif arch=="UNIFIED-FIXED":
        b=max(blocks.values());t=tree(sum(counts.values()),b);logical=paths=3;bucket_blocks=3*t["path_blocks"];bytes_=3*t["path_bytes"];rounds=3;server=t["tree_bytes"];pos=t["position_bytes"];dummy=0;tree_desc=f"unified:{t['height']}";block_desc=f"unified:{b}";n_desc=f"unified:{sum(counts.values())}"
    elif arch in ("UNIFIED-PACKED","RANDOMIZED-PARTITION"):
        fac,pages,n=packed_layout(counts,rec);t=tree(n,PACK_BLOCK);data_pages=math.ceil(rec["data"]/PACK_BLOCK);source=.5*data_pages+.5;logical=source+2;mult=2 if arch=="RANDOMIZED-PARTITION" else 1;paths=logical*mult;pt=t if arch=="UNIFIED-PACKED" else tree(math.ceil(n/8*1.25)+2,PACK_BLOCK);bucket_blocks=paths*pt["path_blocks"];bytes_=paths*pt["path_bytes"];rounds=math.ceil(logical)*mult;server=(t["tree_bytes"] if arch=="UNIFIED-PACKED" else 8*pt["tree_bytes"]);pos=n*4+(n*8 if arch=="RANDOMIZED-PARTITION" else 0);dummy=0;tree_desc=(f"unified-packed:{t['height']}" if arch=="UNIFIED-PACKED" else f"8 partitions:{pt['height']}");block_desc=f"packed:{PACK_BLOCK}";n_desc=f"packed-pages:{n}"
    elif arch=="HYBRID-P":add("data");add("hist",2);rounds=2;trusted=counts["perm"]*rec["perm"];server-=trees["perm"]["tree_bytes"];pos-=trees["perm"]["position_bytes"];dummy=1/3;tree_desc=f"data:{trees['data']['height']};hist:{trees['hist']['height']}";block_desc=f"data:{blocks['data']};hist:{blocks['hist']}";n_desc=f"data:{counts['data']};hist:{counts['hist']}"
    elif arch=="HYBRID-PH":add("data");rounds=1;trusted=counts["perm"]*rec["perm"]+counts["hist"]*rec["hist"];server=trees["data"]["tree_bytes"];pos=trees["data"]["position_bytes"];dummy=.5;tree_desc=f"data:{trees['data']['height']}";block_desc=f"data:{blocks['data']}";n_desc=f"data:{counts['data']}"
    elif arch=="SCAN-PERMISSION":add("data");add("hist",2);logical=3;bytes_+=counts["perm"]*rec["perm"];rounds=3;server=trees["data"]["tree_bytes"]+trees["hist"]["tree_bytes"]+counts["perm"]*rec["perm"];pos=trees["data"]["position_bytes"]+trees["hist"]["position_bytes"];dummy=1/4;tree_desc=f"data:{trees['data']['height']};hist:{trees['hist']['height']};perm:scan";block_desc=f"data:{blocks['data']};hist:{blocks['hist']};perm:{rec['perm']}";n_desc=f"data:{counts['data']};hist:{counts['hist']};perm-scan:{counts['perm']}"
    elif arch=="SCAN-HISTORY":add("data");add("perm");logical=2;bytes_+=2*counts["hist"]*rec["hist"];rounds=3;server=trees["data"]["tree_bytes"]+trees["perm"]["tree_bytes"]+counts["hist"]*rec["hist"];pos=trees["data"]["position_bytes"]+trees["perm"]["position_bytes"];dummy=1/3;tree_desc=f"data:{trees['data']['height']};perm:{trees['perm']['height']};hist:scan";block_desc=f"data:{blocks['data']};perm:{blocks['perm']};hist:{rec['hist']}";n_desc=f"data:{counts['data']};perm:{counts['perm']};hist-scan:{counts['hist']}"
    elif arch=="SCAN-BOTH":add("data");logical=1;bytes_+=counts["perm"]*rec["perm"]+2*counts["hist"]*rec["hist"];rounds=3;server=trees["data"]["tree_bytes"]+counts["perm"]*rec["perm"]+counts["hist"]*rec["hist"];pos=trees["data"]["position_bytes"];dummy=1/3;tree_desc=f"data:{trees['data']['height']};perm:scan;hist:scan";block_desc=f"data:{blocks['data']};perm:{rec['perm']};hist:{rec['hist']}";n_desc=f"data:{counts['data']};perm-scan:{counts['perm']};hist-scan:{counts['hist']}"
    # Analytical read/write mix scales the canonical four dependency slots.
    if mix != {"data":1,"perm":1,"hist_read":1,"hist_write":1}:
        total=sum(mix.values());write_cpu_factor=1+.15*mix["hist_write"]/max(.01,total)
        if arch in ("NAIVE-FIXED","CANONICAL-MODULAR"):
            bytes_=trees["data"]["path_bytes"]*mix["data"]+trees["perm"]["path_bytes"]*mix["perm"]+trees["hist"]["path_bytes"]*(mix["hist_read"]+mix["hist_write"]);paths=logical=total
        elif arch=="UNIFIED-FIXED":
            ut=tree(sum(counts.values()),max(blocks.values()));paths=logical=total;bytes_=paths*ut["path_bytes"]
        elif arch in ("UNIFIED-PACKED","RANDOMIZED-PARTITION"):
            _fac,_pages,n=packed_layout(counts,rec);data_paths=mix["data"]*math.ceil(rec["data"]/PACK_BLOCK);small=mix["perm"]+mix["hist_read"]+mix["hist_write"];logical=data_paths+small;mult=2 if arch=="RANDOMIZED-PARTITION" else 1;paths=logical*mult;pt=tree(math.ceil(n/8*1.25)+2,PACK_BLOCK) if arch=="RANDOMIZED-PARTITION" else tree(n,PACK_BLOCK);bytes_=paths*pt["path_bytes"]
        elif arch=="HYBRID-P":
            logical=paths=mix["data"]+mix["hist_read"]+mix["hist_write"];bytes_=trees["data"]["path_bytes"]*mix["data"]+trees["hist"]["path_bytes"]*(mix["hist_read"]+mix["hist_write"])
        elif arch=="HYBRID-PH":
            logical=paths=mix["data"];bytes_=trees["data"]["path_bytes"]*mix["data"]
        rounds=math.ceil(paths);local_us=paths*18*write_cpu_factor
    else:local_us=paths*18
    physical_4k=bytes_/4096;stash_bytes=6*max(blocks.values());schema_bytes=256 if arch in ("NAIVE-FIXED","CANONICAL-MODULAR") else 0;trusted+=pos+stash_bytes+schema_bytes
    return dict(logical_accesses=logical,physical_paths=paths,physical_blocks=bucket_blocks,physical_blocks_4k_equiv=physical_4k,bytes_action=bytes_,tree_storage_bytes=server,position_map_bytes=pos,stash_bytes=stash_bytes,trusted_state_bytes=trusted,dummy_fraction=dummy,rounds_serial=math.ceil(paths),rounds_parallel=rounds,local_compute_us=local_us,storage_amplification=server/logical_payload,read_write_amplification=bytes_/max(1,rec["data"]+rec["perm"]+rec["hist"]),logical_block_counts=n_desc,block_sizes=block_desc,tree_heights=tree_desc)

def cheapest(rows,budget=16*1048576):return min((r for r in rows if r["privacy"]=="pass" and float(r["trusted_state_bytes"])<=budget),key=lambda x:float(x["bytes_action"]))["architecture"]

def run_stage5(root:Path,n=4000,seeds=(0,1,2)):
    privacy=[];measured=[]
    for seed in seeds:
        eps=[IndependentEpisode(random.Random(seed*99991+i).randrange(64),i%2,True) for i in range(n)];random.Random(seed).shuffle(eps)
        for arch in ARCHS:
            m=Stage5Mediator(arch,seed*1009+3);tr=[];times=[];outs=[];dummies=0
            for e in eps:
                o,t,u,d=m.execute(e);outs.append(o);tr.append(t);times.append(u);dummies+=d
            xs=[privacy_features(t) for t in tr];ys=[e.hidden_state for e in eps];acc,ra=binary_eval(xs,ys,seed);pm=perm_binary(xs,ys,seed)
            privacy.append(dict(seed=seed,architecture=arch,split="random",accuracy=acc,roc_auc=ra,chance=.5,permutation=pm,privacy_expected=PRIVACY[arch]))
            train=[i for i,e in enumerate(eps) if e.entity<48];test=[i for i,e in enumerate(eps) if e.entity>=48];ga,gauc=binary_eval(xs,ys,seed,train,test);sy=list(ys);random.Random(seed+811).shuffle(sy);gp=binary_eval(xs,sy,seed,train,test)[0]
            privacy.append(dict(seed=seed,architecture=arch,split="grouped_entity",accuracy=ga,roc_auc=gauc,chance=.5,permutation=gp,privacy_expected=PRIVACY[arch]))
            measured.append(dict(seed=seed,architecture=arch,mean_latency_us=mean(times),p50_latency_us=percentile(times,.5),p95_latency_us=percentile(times,.95),dummy_fraction=dummies/max(1,sum(len(t) for t in tr))))
    write_csv(root/"results_stage5/privacy_per_seed.csv",privacy);write_csv(root/"results_stage5/measured_latency.csv",measured)
    ps=[]
    for a in ARCHS:
      for split in ("random","grouped_entity"):
        z=[x for x in privacy if x["architecture"]==a and x["split"]==split];ps.append(dict(architecture=a,split=split,accuracy_mean=mean(float(x["accuracy"]) for x in z),accuracy_std=pstdev(float(x["accuracy"]) for x in z),auc_mean=mean(float(x["roc_auc"]) for x in z),auc_std=pstdev(float(x["roc_auc"]) for x in z),permutation_mean=mean(float(x["permutation"]) for x in z),privacy=PRIVACY[a]))
    write_csv(root/"results_stage5/privacy_summary.csv",ps)
    costs=[]
    for regime,counts in REGIMES.items():
        for a in ARCHS:costs.append(dict(regime=regime,architecture=a,privacy=PRIVACY[a],**architecture_cost(a,counts,BASE_REC)))
    write_csv(root/"results_stage5/cost_matrix.csv",costs)
    # Exact Stage-4 equal-record GAAP control under the same path formula.
    data_t=tree(1024,4096);perm_t=tree(1024,4096);hist_t=tree(2048,4096);unified_t=tree(4096,4096)
    matched=[
      dict(architecture="CANONICAL-MODULAR",logical_accesses=4,physical_blocks=data_t["path_blocks"]+perm_t["path_blocks"]+2*hist_t["path_blocks"],bytes_action=data_t["path_bytes"]+perm_t["path_bytes"]+2*hist_t["path_bytes"]),
      dict(architecture="UNIFIED-UNPADDED",logical_accesses=3,physical_blocks=3*unified_t["path_blocks"],bytes_action=3*unified_t["path_bytes"]),
      dict(architecture="UNIFIED-PADDED",logical_accesses=4,physical_blocks=4*unified_t["path_blocks"],bytes_action=4*unified_t["path_bytes"]),
    ]
    write_csv(root/"results_stage5/gaap_matched_control.csv",matched)
    # Crossover sweeps.
    history=[]
    for hn in (64,256,1024,4096,16384,65536,262144):
        counts={**REGIMES["M"],"hist":hn};rows=[]
        for a in ARCHS:
            r=dict(history_records=hn,architecture=a,privacy=PRIVACY[a],**architecture_cost(a,counts,BASE_REC));history.append(r);rows.append(r)
    write_csv(root/"results_stage5/history_growth.csv",history)
    record=[]
    for ds in (512,1024,4096,16384):
      for psiz in (64,128,256,512):
       for hs in (64,256,1024):
        rec={"data":ds,"perm":psiz,"hist":hs}
        for a in ARCHS:record.append(dict(data_record_bytes=ds,permission_record_bytes=psiz,history_record_bytes=hs,architecture=a,privacy=PRIVACY[a],**architecture_cost(a,REGIMES["M"],rec)))
    write_csv(root/"results_stage5/record_size_crossover.csv",record)
    scans=[]
    for target,sizes in (("permission",(64,128,256,512)),("history",(64,128,256,1024))):
      for record_bytes in sizes:
       for small_n in (4,8,16,32,64,128,256,512,1024,2048,4096):
        counts=dict(REGIMES["M"]);counts["perm" if target=="permission" else "hist"]=small_n
        rec=dict(BASE_REC);rec["perm" if target=="permission" else "hist"]=record_bytes
        scan_arch="SCAN-PERMISSION" if target=="permission" else "SCAN-HISTORY"
        for a in ("CANONICAL-MODULAR",scan_arch):
          cost=architecture_cost(a,counts,rec)
          for profile,p in PROFILES.items():
            modeled_ms=float(cost["rounds_parallel"])*p["rtt_ms"]+float(cost["bytes_action"])/(p["mbps"]*125)+float(cost["local_compute_us"])/1000
            scans.append(dict(target=target,record_count=small_n,record_bytes=record_bytes,profile=profile,architecture=a,privacy=PRIVACY[a],modeled_parallel_ms=modeled_ms,**cost))
    write_csv(root/"results_stage5/fixed_scan_crossover.csv",scans)
    store=[]
    for ratio in (1,4,16,64,256):
        counts={"data":4096*ratio,"perm":1024,"hist":4096}
        for a in ARCHS:store.append(dict(data_security_ratio=ratio,architecture=a,privacy=PRIVACY[a],**architecture_cost(a,counts,BASE_REC)))
    write_csv(root/"results_stage5/store_size_crossover.csv",store)
    memory=[]
    for budget_mib in (1,4,16,64,256):
        budget=budget_mib*1048576
        for regime,counts in REGIMES.items():
            pbytes=counts["perm"]*BASE_REC["perm"];phbytes=pbytes+counts["hist"]*BASE_REC["hist"]
            fits="HYBRID-PH" if phbytes<=budget else ("HYBRID-P" if pbytes<=budget else "neither")
            candidates=[a for a in ARCHS if PRIVACY[a]=="pass" and not (a=="HYBRID-P" and pbytes>budget) and not (a=="HYBRID-PH" and phbytes>budget)]
            vals=[dict(architecture=a,**architecture_cost(a,counts,BASE_REC)) for a in candidates];best=min(vals,key=lambda x:x["bytes_action"])
            memory.append(dict(budget_mib=budget_mib,regime=regime,permission_bytes=pbytes,permission_history_bytes=phbytes,hybrid_fit=fits,lowest_bytes_architecture=best["architecture"],lowest_bytes_action=best["bytes_action"]))
    write_csv(root/"results_stage5/trusted_memory_crossover.csv",memory)
    mixes={"read_heavy":{"data":1,"perm":1,"hist_read":.2,"hist_write":.25},"balanced":{"data":1,"perm":1,"hist_read":.5,"hist_write":1},"write_heavy":{"data":1,"perm":1,"hist_read":1,"hist_write":2}}
    mixrows=[]
    for name,mix in mixes.items():
        for a in ("CANONICAL-MODULAR","UNIFIED-FIXED","UNIFIED-PACKED","RANDOMIZED-PARTITION","HYBRID-P","HYBRID-PH"):mixrows.append(dict(mix=name,architecture=a,privacy=PRIVACY[a],**architecture_cost(a,REGIMES["M"],BASE_REC,mix)))
    write_csv(root/"results_stage5/read_write_mix.csv",mixrows)
    network=[]
    for r in costs:
        if r["privacy"]!="pass":continue
        for name,p in PROFILES.items():
            serial=float(r["rounds_serial"])*p["rtt_ms"]+float(r["bytes_action"])/(p["mbps"]*125)+float(r["local_compute_us"])/1000
            parallel=float(r["rounds_parallel"])*p["rtt_ms"]+float(r["bytes_action"])/(p["mbps"]*125)+float(r["local_compute_us"])/1000
            network.append(dict(regime=r["regime"],architecture=r["architecture"],profile=name,rtt_ms=p["rtt_ms"],bandwidth_mbps=p["mbps"],modeled_serial_ms=serial,modeled_parallel_ms=parallel))
    write_csv(root/"results_stage5/network_model.csv",network)
    # Primary figures, maximum four.
    winners=[]
    for reg in REGIMES:
        subset=[r for r in costs if r["regime"]==reg];w=cheapest(subset);winners.append(next(float(r["bytes_action"])/1048576 for r in subset if r["architecture"]==w))
    svg_bar(root/"figures_stage5/figure1_regime_min_cost.svg","Minimum privacy-sufficient transfer by regime",list(REGIMES),winners,"MiB/action",max(winners)*1.15)
    srows=[r for r in memory if r["regime"]=="M"];svg_bar(root/"figures_stage5/figure2_trusted_memory.svg","Medium regime: minimum transfer by trusted budget",[str(r["budget_mib"]) for r in srows],[float(r["lowest_bytes_action"])/1048576 for r in srows],"MiB/action",max(float(r["lowest_bytes_action"])/1048576 for r in srows)*1.15)
    ratio_vals=[]
    for ratio in (1,4,16,64,256):
        z=[r for r in store if int(r["data_security_ratio"])==ratio and r["architecture"] in ("CANONICAL-MODULAR","UNIFIED-PACKED")];ratio_vals.append(min(float(r["bytes_action"])/1048576 for r in z))
    svg_bar(root/"figures_stage5/figure3_heterogeneity.svg","Best privacy-valid canonical/unified-packed cost",["1","4","16","64","256"],ratio_vals,"MiB/action",max(ratio_vals)*1.15)
    mcost=[r for r in costs if r["regime"]=="M" and r["privacy"]=="pass"];svg_scatter(root/"figures_stage5/figure4_pareto.svg",[r["architecture"] for r in mcost],[float(r["bytes_action"])/1048576 for r in mcost],[mean(float(x["p95_latency_us"]) for x in measured if x["architecture"]==r["architecture"])/1000 for r in mcost])
    return ps,costs,measured,memory

from __future__ import annotations

import json
import math
import os
import socketserver
import threading
import time
from pathlib import Path

from .protocol import branch_label,canonical_json,opaque_token,recv_frame,seal,send_frame,unseal

PROFILES={
 "LOCAL-LAN":{"rtt_ms":.5,"bandwidth_mbps":1000},
 "ENTERPRISE-DC":{"rtt_ms":2.0,"bandwidth_mbps":200},
 "REMOTE-CLOUD":{"rtt_ms":20.0,"bandwidth_mbps":50},
}

REGIMES={
 "SMALL":{"data_count":256,"permission_count":128,"history_count":256,"data_bytes":512,"permission_bytes":128,"history_bytes":256},
 "MEDIUM":{"data_count":8192,"permission_count":1024,"history_count":4096,"data_bytes":1024,"permission_bytes":128,"history_bytes":256},
 "LARGE":{"data_count":65536,"permission_count":16384,"history_count":131072,"data_bytes":4096,"permission_bytes":256,"history_bytes":512},
 "HETEROGENEOUS":{"data_count":65536,"permission_count":512,"history_count":8192,"data_bytes":4096,"permission_bytes":64,"history_bytes":128},
 "EQUAL-RECORD":{"data_count":1024,"permission_count":1024,"history_count":2048,"data_bytes":4096,"permission_bytes":4096,"history_bytes":4096},
}

def path_bytes(count,block_bytes,accesses=1,z=4):
    height=max(1,math.ceil(math.log2(max(2,count))))
    return accesses*2*(height+1)*z*block_bytes

def protected(payload,logical_oram_bytes=0,server_compute_us=0):
    # JSON-safe ciphertext-transfer padding is real serialized wire data. It is
    # deliberately compressibility-agnostic because no compression is used.
    return {"protected":seal(payload),"oram_transfer":"A"*logical_oram_bytes,
            "logical_oram_bytes":logical_oram_bytes,"server_compute_us":server_compute_us}

class ServiceState:
    def __init__(self,kind,config):
        self.kind=kind;self.config=config;self.lock=threading.RLock()
        self.permissions={};self.permission_versions={};self.logs={};self.seen={};self.effects={}
    def permission(self,tenant):
        return self.permissions.get(tenant,True),self.permission_versions.get(tenant,1)
    def history(self,tenant):return self.logs.setdefault(tenant,[])
    def dispatch(self,msg):
        if msg.get("op")=="ping":return {"ok":True,"pid":os.getpid(),"kind":self.kind}
        body=unseal(msg["protected"]) if "protected" in msg else {}
        tenant=body.get("tenant",msg.get("tenant","default"));mode=msg.get("mode","direct")
        start=time.perf_counter_ns();logical=0
        with self.lock:
            if self.kind=="private":
                size=self.config["data_bytes"];content="Q"*max(1,size-96)
                value={"recipient":"finance.owner@example.invalid","subject":"Synthetic Project Aurora quote","document":"synthetic_document_18:"+content}
                if mode=="oram":logical=path_bytes(self.config["data_count"],size,2)
                result=protected(value,logical)
            elif self.kind=="permission":
                if msg["op"]=="admin_set":
                    self.permissions[tenant]=bool(body["allow"]);self.permission_versions[tenant]=self.permission_versions.get(tenant,1)+1
                    result=protected({"allow":self.permissions[tenant],"version":self.permission_versions[tenant]})
                else:
                    allow,version=self.permission(tenant);pad="P"*max(0,self.config["permission_bytes"]-40)
                    value={"allow":allow,"version":version,"history_required":branch_label(body["request_id"]),"padding":pad}
                    if mode=="oram":logical=path_bytes(self.config["permission_count"],self.config["permission_bytes"])
                    result=protected(value,logical)
            elif self.kind=="history":
                log=self.history(tenant)
                if msg["op"]=="seed":
                    count=int(body["count"]);log.clear();self.seen[tenant]=set()
                    for i in range(count):
                        rid=f"seed-{i}";log.append({"request_id":rid,"event":"synthetic_disclosure","device":"other_device","padding":"L"*max(0,self.config["history_bytes"]-96)});self.seen[tenant].add(rid)
                    result=protected({"version":len(log)})
                elif msg["op"] in ("get","sync","oram_access"):
                    since=int(body.get("since",0));events=log[since:]
                    if msg["op"] in ("get","oram_access"):events=log[-1:]
                    value={"version":len(log),"events":events,"padding":"H"*max(0,self.config["history_bytes"]-48)}
                    if mode=="oram":logical=path_bytes(self.config["history_count"],self.config["history_bytes"])
                    result=protected(value,logical)
                elif msg["op"]=="append":
                    rid=body["request_id"]
                    if rid not in self.seen.setdefault(tenant,set()):
                        log.append({"request_id":rid,"event":"synthetic_disclosure","device":body["device"],"padding":"L"*max(0,self.config["history_bytes"]-96)});self.seen[tenant].add(rid)
                    if mode=="oram":logical=path_bytes(self.config["history_count"],self.config["history_bytes"])
                    result=protected({"version":len(log),"duplicate":rid in self.seen[tenant]},logical)
                elif msg["op"]=="snapshot":result=protected({"version":len(log),"request_ids":[x["request_id"] for x in log]})
                else:raise ValueError(msg["op"])
            elif self.kind=="unified":
                allow,version=self.permission(tenant);log=self.history(tenant)
                if msg["op"]=="seed":
                    count=int(body["count"]);log.clear();self.seen[tenant]=set()
                    for i in range(count):
                        rid=f"seed-{i}";log.append({"request_id":rid,"event":"synthetic_disclosure","device":"other_device"});self.seen[tenant].add(rid)
                    result=protected({"version":len(log)})
                elif msg["op"]=="admin_set":
                    self.permissions[tenant]=bool(body["allow"]);self.permission_versions[tenant]=self.permission_versions.get(tenant,1)+1
                    result=protected({"allow":self.permissions[tenant],"version":self.permission_versions[tenant]})
                elif msg["op"]=="batch_access":
                    content="Q"*max(1,self.config["data_bytes"]-96)
                    value={"recipient":"finance.owner@example.invalid","subject":"Synthetic Project Aurora quote","document":"synthetic_document_18:"+content,"allow":allow,"permission_version":version,"history_required":branch_label(body["request_id"]),"history_version":len(log),"events":log[-1:]}
                    largest=max(self.config["data_bytes"],self.config["permission_bytes"],self.config["history_bytes"])
                    logical=path_bytes(self.config["data_count"]+self.config["permission_count"]+self.config["history_count"],largest,4)
                    result=protected(value,logical)
                elif msg["op"]=="append":
                    rid=body["request_id"]
                    if rid not in self.seen.setdefault(tenant,set()):log.append({"request_id":rid,"event":"synthetic_disclosure","device":body["device"]});self.seen[tenant].add(rid)
                    largest=max(self.config["data_bytes"],self.config["permission_bytes"],self.config["history_bytes"])
                    logical=path_bytes(sum(self.config[k] for k in ("data_count","permission_count","history_count")),largest)
                    result=protected({"version":len(log)},logical)
                elif msg["op"]=="snapshot":result=protected({"version":len(log),"request_ids":[x["request_id"] for x in log]})
                else:raise ValueError(msg["op"])
            elif self.kind=="tool":
                rid=body["request_id"]
                duplicate=rid in self.effects.setdefault(tenant,set())
                if not duplicate:self.effects[tenant].add(rid)
                result=protected({"status":"sent","duplicate":duplicate,"effect_count":len(self.effects[tenant])})
            else:raise ValueError(self.kind)
        result["server_compute_us"]=(time.perf_counter_ns()-start)/1000
        return result

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        msg,request_bytes=recv_frame(self.request);response=self.server.state.dispatch(msg)
        raw_len=len(canonical_json(response))+4;profile=self.server.profile
        delay=profile["rtt_ms"]/1000+(request_bytes+raw_len)/(profile["bandwidth_mbps"]*125000)
        if delay>0:time.sleep(delay)
        send_frame(self.request,response)

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True;daemon_threads=True

def service_process(kind,port,profile_name,config,ready):
    with Server(("127.0.0.1",port),Handler) as server:
        server.state=ServiceState(kind,config);server.profile=PROFILES[profile_name];ready.set();server.serve_forever()

def observer_process(queue,path,ready):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);ready.set()
    with path.open("w",encoding="utf-8") as f:
        while True:
            item=queue.get()
            if item is None:break
            f.write(json.dumps(item,separators=(",",":"),sort_keys=True)+"\n");f.flush()

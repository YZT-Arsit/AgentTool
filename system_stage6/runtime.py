from __future__ import annotations

import concurrent.futures
import multiprocessing
import os
import re
import socketserver
import tempfile
import time
from pathlib import Path

from .protocol import opaque_token,recv_frame,reserve_port,rpc,seal,send_frame,unseal
from .services import Handler,PROFILES,REGIMES,Server,observer_process,service_process

ARCHITECTURES=("DIRECT-MODULAR","INDEPENDENT-MODULAR-ORAM","FIXED-CANONICAL-MODULAR","UNIFIED-ORAM","HYBRID-P","HYBRID-PH")
PRIVACY={"DIRECT-MODULAR":"fail","INDEPENDENT-MODULAR-ORAM":"fail","FIXED-CANONICAL-MODULAR":"pass","UNIFIED-ORAM":"pass","HYBRID-P":"pass","HYBRID-PH":"pass"}

def _visible_event(endpoint,op,res):
    return {"endpoint":endpoint,"operation":op,"request_bytes":res.request_bytes,"response_bytes":res.response_bytes,"wall_start_ns":res.wall_start_ns,"wall_end_ns":res.wall_end_ns,"duration_ms":res.duration_ms,"connection_reused":False,"logical_oram_bytes":res.response.get("logical_oram_bytes",0)}

class MediatorEngine:
    def __init__(self,architecture,ports,observer_queue,config):
        self.architecture=architecture;self.ports=ports;self.observer_queue=observer_queue;self.config=config
        self.permission_cache={};self.history_cache={}
    def call(self,endpoint,op,body,mode="direct",visible_op=None):
        outer={"op":op,"mode":mode,"protected":seal(body)}
        if mode=="direct":outer["address"]=opaque_token(endpoint,body.get("tenant","")+":"+body.get("request_id",""))
        else:outer["path_request"]="oblivious_path"
        res=rpc(self.ports[endpoint],outer);event=_visible_event(endpoint,visible_op or op,res);event["episode"]=opaque_token("episode",body.get("request_id","administrative"));self.observer_queue.put(event)
        return unseal(res.response["protected"]),event,float(res.response.get("server_compute_us",0))
    def execute(self,action):
        start=time.perf_counter_ns();events=[];breakdown={"planner_mediator_ms":0,"authorization_ms":0,"private_resolution_ms":0,"oram_compute_ms":0,"freshness_ms":0,"history_sync_ms":0,"tool_ms":0}
        required=("action","recipient","document","user","device","request_id","tenant")
        if any(k not in action for k in required) or action["action"]!="SEND_MESSAGE" or not re.fullmatch(r"CONTACT_\d+",action["recipient"]) or not re.fullmatch(r"DOCUMENT_\d+",action["document"]):
            return {"status":"DENY","reason":"invalid_action","request_id":action.get("request_id","missing"),"host_visible_trace":events,"metrics":{"total_ms":(time.perf_counter_ns()-start)/1e6,"breakdown":breakdown,"trusted_cache_bytes":0}}
        tenant=action["tenant"];base={"tenant":tenant,"request_id":action["request_id"],"device":action["device"],"recipient":action["recipient"],"document":action["document"]}
        mode="direct" if self.architecture=="DIRECT-MODULAR" else "oram"
        compute=0
        if self.architecture=="UNIFIED-ORAM":
            t=time.perf_counter_ns();value,e,c=self.call("unified","batch_access",{**base,"since":0},"oram","oram_batch");events.append(e);compute+=c;breakdown["private_resolution_ms"]=(time.perf_counter_ns()-t)/1e6
            private=value;permission={"allow":value["allow"],"version":value["permission_version"],"history_required":value["history_required"]};history={"version":value["history_version"],"events":value["events"]}
        else:
            def private_call():return self.call("private","get",base,mode,"direct_read" if mode=="direct" else "oram_access")
            perm_op="validate" if self.architecture.startswith("HYBRID") else ("get" if mode=="direct" else "oram_access")
            perm_mode="direct" if self.architecture.startswith("HYBRID") else mode
            def perm_call():return self.call("permission",perm_op,base,perm_mode,"version_validate" if self.architecture.startswith("HYBRID") else ("direct_read" if mode=="direct" else "oram_access"))
            run_history=self.architecture not in ("DIRECT-MODULAR","INDEPENDENT-MODULAR-ORAM")
            history_op="sync" if self.architecture=="HYBRID-PH" else ("get" if mode=="direct" else "oram_access")
            cache_key=(tenant,action["device"])
            hist_body={**base,"since":self.history_cache.get(cache_key,(0,[]))[0] if self.architecture=="HYBRID-PH" else 0}
            def hist_call():return self.call("history",history_op,hist_body,"direct" if self.architecture=="HYBRID-PH" else mode,"history_sync" if self.architecture=="HYBRID-PH" else ("direct_read" if mode=="direct" else "oram_access"))
            t=time.perf_counter_ns()
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                fp=pool.submit(private_call);fa=pool.submit(perm_call);fh=pool.submit(hist_call) if run_history else None
                private,ep,cp=fp.result();permission,ea,ca=fa.result();history_tuple=fh.result() if fh else None
            events.extend((ep,ea));compute+=cp+ca
            if history_tuple:
                history,eh,ch=history_tuple;events.append(eh);compute+=ch
            else:history={"version":0,"events":[]}
            breakdown["private_resolution_ms"]=(time.perf_counter_ns()-t)/1e6
            if not run_history and permission["history_required"]:
                history,eh,ch=hist_call();events.append(eh);compute+=ch
            if self.architecture in ("HYBRID-P","HYBRID-PH"):
                self.permission_cache[(tenant,action["device"])]=(permission["version"],permission["allow"]);breakdown["freshness_ms"]=ea["duration_ms"]
            if self.architecture=="HYBRID-PH":
                prior_events=self.history_cache.get(cache_key,(0,[]))[1]
                self.history_cache[cache_key]=(history["version"],[*prior_events,*history["events"]]);breakdown["history_sync_ms"]=eh["duration_ms"]
                # The value is intentionally kept inside mediator memory. The
                # experiment's policy only needs existence/count, but retaining
                # ordered bodies makes this a real history cache rather than a
                # version-only freshness token.
                _history_consulted=len(self.history_cache[cache_key][1]) if permission["history_required"] else 0
        breakdown["authorization_ms"]=next((e["duration_ms"] for e in events if e["endpoint"] in ("permission","unified")),0)
        breakdown["oram_compute_ms"]=compute/1000
        if not permission["allow"]:
            return {"status":"DENY","reason":"revoked","request_id":action["request_id"],"host_visible_trace":events,"metrics":self.metrics(start,events,breakdown)}
        tool_body={**base,"to":private["recipient"],"subject":private["subject"],"document":private["document"]}
        t=time.perf_counter_ns();tool,et,ct=self.call("tool","send",tool_body,"direct","tool_invoke");events.append(et);breakdown["tool_ms"]=(time.perf_counter_ns()-t)/1e6
        append_endpoint="unified" if self.architecture=="UNIFIED-ORAM" else "history"
        append_mode="oram" if self.architecture in ("INDEPENDENT-MODULAR-ORAM","FIXED-CANONICAL-MODULAR","UNIFIED-ORAM","HYBRID-P") else "direct"
        _,eh,ch=self.call(append_endpoint,"append",base,append_mode,"oram_access" if append_mode=="oram" else "history_append");events.append(eh);compute+=ch
        if self.architecture=="HYBRID-PH":
            version,cached_events=self.history_cache[cache_key]
            self.history_cache[cache_key]=(version+1,[*cached_events,{"request_id":action["request_id"],"event":"synthetic_disclosure","device":action["device"]}])
        breakdown["oram_compute_ms"]=compute/1000
        return {"status":"ALLOW","effect":"sent","request_id":action["request_id"],"duplicate_effect":tool["duplicate"],"host_visible_trace":events,"metrics":self.metrics(start,events,breakdown)}
    def metrics(self,start,events,breakdown):
        cache=len(self.permission_cache)*self.config["permission_bytes"]+sum(len(v[1])*self.config["history_bytes"] for v in self.history_cache.values())
        return {"total_ms":(time.perf_counter_ns()-start)/1e6,"breakdown":breakdown,"trusted_cache_bytes":cache,
                "wire_bytes":sum(e["request_bytes"]+e["response_bytes"] for e in events),"remote_requests":len(events),
                "logical_oram_bytes":sum(e["logical_oram_bytes"] for e in events),"freshness_rtts":sum(e["operation"]=="version_validate" for e in events),"history_sync_rtts":sum(e["operation"]=="history_sync" for e in events)}

class MediatorHandler(socketserver.BaseRequestHandler):
    def handle(self):
        msg,_=recv_frame(self.request)
        if msg.get("op")=="ping":response={"ok":True,"pid":os.getpid(),"architecture":self.server.engine.architecture}
        else:response=self.server.engine.execute(unseal(msg["protected"]))
        send_frame(self.request,response)

def mediator_process(architecture,port,ports,observer_queue,config,ready):
    with Server(("127.0.0.1",port),MediatorHandler) as server:
        server.engine=MediatorEngine(architecture,ports,observer_queue,config);ready.set();server.serve_forever()

class PlannerHandler(socketserver.BaseRequestHandler):
    def handle(self):
        msg,_=recv_frame(self.request)
        if msg.get("op")=="ping":response={"ok":True,"pid":os.getpid(),"kind":"planner"}
        else:
            action=msg["action"];port=self.server.mediators[msg["architecture"]]
            forwarded=rpc(port,{"op":"execute","protected":seal(action)},timeout=30);response=forwarded.response
            response["metrics"]["breakdown"]["planner_mediator_ms"]=forwarded.duration_ms
            response["metrics"]["planner_mediator_request_bytes"]=forwarded.request_bytes;response["metrics"]["planner_mediator_response_bytes"]=forwarded.response_bytes
        send_frame(self.request,response)

def planner_process(port,mediators,ready):
    with Server(("127.0.0.1",port),PlannerHandler) as server:
        server.mediators=mediators;ready.set();server.serve_forever()

class Stage6Cluster:
    def __init__(self,profile="LOCAL-LAN",regime="MEDIUM",architectures=ARCHITECTURES,observer_path=None):
        self.profile=profile;self.config=dict(REGIMES[regime]);self.architectures=tuple(architectures);self.ctx=multiprocessing.get_context("spawn")
        self.observer_path=observer_path or str(Path(tempfile.mkdtemp(prefix="stage6_"))/"observer.jsonl")
    def __enter__(self):
        self.queue=self.ctx.Queue();self.processes={};self.ports={k:reserve_port() for k in ("private","permission","history","unified","tool")};ready=[]
        ro=self.ctx.Event();p=self.ctx.Process(target=observer_process,args=(self.queue,self.observer_path,ro),name="observer_logger");p.start();self.processes["observer"]=p;ready.append(ro)
        for kind,port in self.ports.items():
            e=self.ctx.Event();p=self.ctx.Process(target=service_process,args=(kind,port,self.profile,self.config,e),name=f"{kind}_service");p.start();self.processes[kind]=p;ready.append(e)
        self.mediator_ports={a:reserve_port() for a in self.architectures}
        for a,port in self.mediator_ports.items():
            e=self.ctx.Event();p=self.ctx.Process(target=mediator_process,args=(a,port,self.ports,self.queue,self.config,e),name=f"mediator_{a}");p.start();self.processes[f"mediator:{a}"]=p;ready.append(e)
        self.planner_port=reserve_port();e=self.ctx.Event();p=self.ctx.Process(target=planner_process,args=(self.planner_port,self.mediator_ports,e),name="planner_process");p.start();self.processes["planner"]=p;ready.append(e)
        for e in ready:
            if not e.wait(15):raise RuntimeError("Stage-6 process failed to start")
        return self
    def __exit__(self,*exc):
        if hasattr(self,"queue"):self.queue.put(None)
        for p in reversed(list(getattr(self,"processes",{}).values())):
            p.join(.5)
            if p.is_alive():p.terminate();p.join(2)
    @property
    def pids(self):return {k:p.pid for k,p in self.processes.items()}
    def action(self,architecture,request_id,device="employee_device_A",tenant="enterprise",user="employee_7",recipient="CONTACT_7",document="DOCUMENT_18"):
        action={"action":"SEND_MESSAGE","recipient":recipient,"document":document,"user":user,"device":device,"request_id":request_id,"tenant":tenant}
        result=rpc(self.planner_port,{"op":"plan","architecture":architecture,"action":action},timeout=60)
        result.response["metrics"]["end_to_end_ms"]=result.duration_ms
        result.response["metrics"]["driver_planner_request_bytes"]=result.request_bytes;result.response["metrics"]["driver_planner_response_bytes"]=result.response_bytes
        return result.response
    def set_permission(self,allow,tenant="enterprise"):
        body={"tenant":tenant,"allow":allow}
        permission=rpc(self.ports["permission"],{"op":"admin_set","mode":"direct","protected":seal(body)})
        unified=rpc(self.ports["unified"],{"op":"admin_set","mode":"direct","protected":seal(body)})
        return {"permission_wire_bytes":permission.request_bytes+permission.response_bytes,"permission_ms":permission.duration_ms,
                "unified_wire_bytes":unified.request_bytes+unified.response_bytes,"unified_ms":unified.duration_ms}
    def history_snapshot(self,architecture,tenant="enterprise"):
        endpoint="unified" if architecture=="UNIFIED-ORAM" else "history"
        return unseal(rpc(self.ports[endpoint],{"op":"snapshot","mode":"direct","protected":seal({"tenant":tenant})}).response["protected"])
    def seed_history(self,count,tenant="enterprise",unified=False):
        endpoint="unified" if unified else "history"
        return rpc(self.ports[endpoint],{"op":"seed","mode":"direct","protected":seal({"tenant":tenant,"count":count})}).response
    def tool_effect_count(self,tenant="enterprise"):
        # Tool has no public snapshot operation; duplicate status is the tested interface.
        return None

from __future__ import annotations

import hashlib
import hmac
import json
import multiprocessing
import random
import socketserver
import threading
import time
from dataclasses import dataclass

from system_stage6.protocol import canonical_json,recv_frame,reserve_port,rpc,send_frame

VARIANTS=("ORIGINAL-MEDIATOR","PER-SERVICE-ORAM","UNIFIED-OBLIVIOUS","FIXED-CANONICAL","TRUSTED-LOCAL")
TASKS=("SEND_MESSAGE","SHARE_DOCUMENT","CREATE_EVENT","FORWARD_INFORMATION")
STATE_ENDPOINTS=("PRIVATE_DATA_DB","PERMISSION_DB","DISCLOSURE_LOG")
FORBIDDEN=("private_object_id","private_label","hidden_class","permission_value","taint_origin","is_dummy","logical_id","record_key","plaintext")

@dataclass(frozen=True)
class EnterpriseState:
    entity:int
    project:int
    taint_origin:str
    permission_state:str
    consent_state:str
    policy_profile:int
    prior_disclosure:bool

@dataclass(frozen=True)
class UserTask:
    action_type:str
    destination_class:str

@dataclass(frozen=True)
class Episode:
    episode_id:int
    state:EnterpriseState
    task:UserTask
    generation_order:tuple[str,...]=("state","task")

def generate_episode(rng:random.Random,episode_id:int)->Episode:
    # State is sampled first. No evaluation label exists at this point.
    state=EnterpriseState(
        entity=rng.randrange(96),project=rng.randrange(24),
        taint_origin="direct_private_db" if rng.random()<.5 else "persistent_transitive",
        permission_state=rng.choices(("ALLOW","DENY","MISSING"),(.42,.28,.30))[0],
        consent_state="ALLOW" if rng.random()<.72 else "DENY",
        policy_profile=rng.randrange(6),prior_disclosure=rng.random()<.55)
    # The task is sampled only after enterprise state exists and independently
    # of its private attributes.
    task=UserTask(TASKS[rng.randrange(len(TASKS))],("peer","vendor","internal")[rng.randrange(3)])
    return Episode(episode_id,state,task)

def ground_truth(e:Episode):
    # Labels are derived after generation/execution by the experiment harness.
    return {"episode_id":e.episode_id,"entity":e.state.entity,"project":e.state.project,
            "policy_profile":e.state.policy_profile,
            "requires_history":int(e.state.taint_origin=="persistent_transitive"),
            "permission_missing":int(e.state.permission_state=="MISSING"),
            "initial_permission":e.state.permission_state,
            "consent":e.state.consent_state,"prior_disclosure":int(e.state.prior_disclosure),
            "action_type":e.task.action_type}

class _AckState:
    def __init__(self,kind):self.kind=kind
    def dispatch(self,msg):
        # Bodies are opaque to the observer; fixed payload avoids adding a
        # designer-selected response-size label.
        return {"ok":True,"protected":"R"*192,"service":self.kind}

class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        msg,_=recv_frame(self.request);send_frame(self.request,self.server.state.dispatch(msg))

class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True;daemon_threads=True

def _service_process(kind,port,ready):
    with _Server(("127.0.0.1",port),_Handler) as server:
        server.state=_AckState(kind);ready.set();server.serve_forever()

class ServiceCluster:
    """Actual localhost processes used only as synthetic observable services."""
    def __init__(self):
        self.ctx=multiprocessing.get_context("spawn");self.ports={};self.processes=[]
        for kind in (*STATE_ENDPOINTS,"UNIFIED_STATE","USER_CONSENT","MESSAGE_TOOL","DOCUMENT_TOOL","CALENDAR_TOOL","FORWARD_TOOL"):
            port=reserve_port();ready=self.ctx.Event();p=self.ctx.Process(target=_service_process,args=(kind,port,ready));p.start()
            if not ready.wait(10):raise RuntimeError("stage8 service did not start")
            self.ports[kind]=port;self.processes.append(p)
    def close(self):
        for p in self.processes:
            if p.is_alive():p.terminate()
        for p in self.processes:p.join(5)
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

class TraceTransport:
    def __init__(self,cluster:ServiceCluster,variant:str,seed:int):
        self.cluster=cluster;self.variant=variant;self.rng=random.Random(seed);self.events=[];self.action_index=0;self.action_type=""
        self.key=hashlib.sha256(f"stage8-observer-token:{seed}".encode()).digest()
    def begin_action(self,action_type,index):self.action_type=action_type;self.action_index=index
    def _token(self,semantic,address):return hmac.new(self.key,f"{semantic}:{address}".encode(),hashlib.sha256).hexdigest()[:20]
    def call(self,destination,semantic,address="none",oram=False):
        visible_op="ORAM_ACCESS" if oram else semantic
        path_id=self.rng.randrange(256) if oram else None
        msg={"op":visible_op,"protected":"Q"*192}
        if oram:msg["physical_path"]=path_id
        else:msg["stable_address"]=self._token(destination,address)
        result=rpc(self.cluster.ports[destination],msg)
        event={"timestamp_ns":result.wall_start_ns,"source_process":"TRUSTED_MEDIATOR","destination_service":destination,
               "operation_class":visible_op,"request_bytes":result.request_bytes,"response_bytes":result.response_bytes,
               "duration_us":round(result.duration_ms*1000,3),"action_index":self.action_index,
               "public_action_type":self.action_type,"connection_reused":False}
        if oram:event["physical_path"]=path_id
        else:event["stable_address"]=msg["stable_address"]
        self.events.append(event);return result

class SourceFaithfulMediator:
    """SOURCE-FAITHFUL REFERENCE IMPLEMENTATION, not GAAP code.

    It executes GAAP-documented private-data lookup, persistent-taint recovery,
    permission evaluation/acquisition, intercepted tool effect, and disclosure
    logging. Endpoint separation and oblivious baselines are project deployment
    choices, not claims about GAAP's implementation.
    """
    def __init__(self,variant,transport):self.variant=variant;self.t=transport
    def _state_access(self,endpoint,semantic,address):
        if self.variant=="TRUSTED-LOCAL":return
        if self.variant=="UNIFIED-OBLIVIOUS":self.t.call("UNIFIED_STATE","state",oram=True);return
        self.t.call(endpoint,semantic,address,oram=self.variant in ("PER-SERVICE-ORAM","FIXED-CANONICAL"))
    def _origin_and_permission(self,e,current_permission):
        s=e.state
        if self.variant=="FIXED-CANONICAL":
            # Known fixed-trace technique: both maximum origin dependencies and
            # the permission slot execute. Real-vs-padding status stays trusted.
            self._state_access("PRIVATE_DATA_DB","READ",f"entity:{s.entity}")
            self._state_access("DISCLOSURE_LOG","READ",f"provenance:{s.entity}")
            self._state_access("PERMISSION_DB","READ",f"policy:{s.entity}:{s.policy_profile}")
            self._state_access("PERMISSION_DB","WRITE",f"policy-write:{s.entity}:{s.policy_profile}")
            self._state_access("DISCLOSURE_LOG","WRITE",f"effect:{e.episode_id}")
        else:
            if s.taint_origin=="direct_private_db":self._state_access("PRIVATE_DATA_DB","READ",f"entity:{s.entity}")
            else:self._state_access("DISCLOSURE_LOG","READ",f"provenance:{s.entity}")
            self._state_access("PERMISSION_DB","READ",f"policy:{s.entity}:{s.policy_profile}")
        return current_permission
    def _permission_write(self,e):
        if self.variant=="FIXED-CANONICAL":return
        self._state_access("PERMISSION_DB","WRITE",f"policy:{e.state.entity}:{e.state.policy_profile}")
    def _history_write(self,e):
        if self.variant=="FIXED-CANONICAL":return
        self._state_access("DISCLOSURE_LOG","WRITE",f"effect:{e.episode_id}")
    def _tool(self,e):
        endpoint={"SEND_MESSAGE":"MESSAGE_TOOL","SHARE_DOCUMENT":"DOCUMENT_TOOL","CREATE_EVENT":"CALENDAR_TOOL","FORWARD_INFORMATION":"FORWARD_TOOL"}[e.task.action_type]
        self.t.call(endpoint,"EFFECT",f"effect:{e.episode_id}",oram=False)
    def execute(self,e:Episode):
        current=e.state.permission_state;attempt=0;effects=0;outcomes=[]
        while True:
            self.t.begin_action(e.task.action_type,attempt);attempt+=1
            decision=self._origin_and_permission(e,current)
            if decision=="MISSING":
                self.t.call("USER_CONSENT","PROMPT",f"consent:{e.episode_id}",oram=False)
                current=e.state.consent_state;self._permission_write(e);outcomes.append("CONSENT_ACQUIRED")
                continue
            if decision=="ALLOW":
                self._tool(e);effects+=1;self._history_write(e);outcomes.append("EFFECT_COMMITTED")
            else:outcomes.append("DENIED")
            break
        return {"authorized":current=="ALLOW","effect_count":effects,"final_outcome":outcomes[-1],
                "attempts":attempt,"action_type":e.task.action_type},list(self.t.events)

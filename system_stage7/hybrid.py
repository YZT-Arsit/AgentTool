from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .durable_oram import atomic_json,read_json

class AuthorityUnavailable(RuntimeError):pass

class EnterpriseAuthority:
    def __init__(self,path=None):
        self.lock=threading.RLock();self.path=Path(path) if path else None;self.available=True
        state=read_json(self.path) if self.path and self.path.exists() else {"allow":True,"permission_version":1,"history":[]}
        self.allow=bool(state["allow"]);self.permission_version=int(state["permission_version"]);self.history=list(state["history"]);self._persist()
    def _persist(self):
        if self.path:atomic_json(self.path,{"allow":self.allow,"permission_version":self.permission_version,"history":self.history})
    def set_permission(self,allow):
        with self.lock:self.allow=bool(allow);self.permission_version+=1;self._persist()
    def permission(self):
        if not self.available:raise AuthorityUnavailable("authoritative state unavailable")
        with self.lock:return {"allow":self.allow,"version":self.permission_version,"epoch":1}
    def append(self,event_id,device="device"):
        if not self.available:raise AuthorityUnavailable("authoritative state unavailable")
        with self.lock:
            if not any(e["event_id"]==event_id for e in self.history):self.history.append({"event_id":event_id,"version":len(self.history)+1,"device":device});self._persist()
            return len(self.history)
    def sync(self,since):
        if not self.available:raise AuthorityUnavailable("authoritative state unavailable")
        with self.lock:return {"version":len(self.history),"events":[dict(e) for e in self.history[since:]],"epoch":1}

class HybridRecoveryClient:
    def __init__(self,authority,with_history=False):self.authority=authority;self.with_history=with_history;self.permission_cache=None;self.history_version=0;self.history=[];self.cache_valid=False;self.last_recovery={}
    def snapshot(self):return json.dumps({"permission":self.permission_cache,"history_version":self.history_version,"history":self.history,"with_history":self.with_history},sort_keys=True).encode()
    def restore(self,snapshot):
        data=json.loads(snapshot);self.permission_cache=data["permission"];self.history_version=int(data["history_version"]);self.history=list(data["history"]);self.cache_valid=False
    def recover(self):
        start=time.perf_counter_ns();wire=0;rtts=0
        try:
            current=self.authority.permission();wire+=len(json.dumps(current))+32;rtts+=1;self.permission_cache=current
            if self.with_history:
                delta=self.authority.sync(self.history_version);wire+=len(json.dumps(delta))+32;rtts+=1;self.history.extend(delta["events"]);self.history_version=delta["version"]
            self.cache_valid=True;status="ready"
        except AuthorityUnavailable:
            self.cache_valid=False;status="defer"
        self.last_recovery={"status":status,"bytes":wire,"rtts":rtts,"latency_ms":(time.perf_counter_ns()-start)/1e6};return status
    def authorize(self):
        # Every action revalidates even after successful recovery.
        try:self.permission_cache=self.authority.permission();self.cache_valid=True
        except AuthorityUnavailable:self.cache_valid=False;return "DEFER"
        return "ALLOW" if self.permission_cache["allow"] else "DENY"
    def synchronize_history(self):
        if not self.with_history:return
        delta=self.authority.sync(self.history_version);self.history.extend(delta["events"]);self.history_version=delta["version"]
    def cache_bytes(self):return len(self.snapshot())

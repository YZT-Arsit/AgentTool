from __future__ import annotations

import json
import hashlib
import threading
from pathlib import Path

from .durable_oram import CrashInjected,atomic_json,read_json

class EffectFailure(RuntimeError):pass

class IdempotentTool:
    def __init__(self,path=None):
        self.lock=threading.Lock();self.path=Path(path) if path else None;self.effects=read_json(self.path) if self.path and self.path.exists() else {};self.fail_mode=None
    def _persist(self):
        if self.path:atomic_json(self.path,self.effects)
    def execute(self,operation_id,payload):
        with self.lock:
            if self.fail_mode=="before_effect":raise EffectFailure("tool unavailable")
            payload_digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
            duplicate=operation_id in self.effects
            if duplicate and self.effects[operation_id]["payload_digest"]!=payload_digest:raise EffectFailure("operation identifier payload mismatch")
            if not duplicate:self.effects[operation_id]={"status":"sent","payload_digest":payload_digest};self._persist()
            result=dict(self.effects[operation_id]);result["duplicate"]=duplicate
            if self.fail_mode in ("timeout_after_effect","drop_after_effect"):raise TimeoutError("ambiguous tool result")
            return result
    def query(self,operation_id):return self.effects.get(operation_id)

class AuthoritativeDisclosureLog:
    def __init__(self,path):
        self.path=Path(path);self.lock=threading.RLock();self.fail_commit=False
        self.state=read_json(self.path) if self.path.exists() else {"next_version":1,"operations":{}}
        self._persist()
    def _persist(self):atomic_json(self.path,self.state)
    def prepare(self,operation_id):
        with self.lock:
            self.state["operations"].setdefault(operation_id,{"status":"PREPARED","version":None});self._persist()
    def commit(self,operation_id):
        with self.lock:
            if self.fail_commit:self.fail_commit=False;raise EffectFailure("audit commit unavailable")
            item=self.state["operations"].setdefault(operation_id,{"status":"PREPARED","version":None})
            if item["status"]!="COMMITTED":item["status"]="COMMITTED";item["version"]=self.state["next_version"];self.state["next_version"]+=1
            self._persist();return item["version"]
    def abort(self,operation_id):
        with self.lock:
            item=self.state["operations"].get(operation_id)
            if item and item["status"]!="COMMITTED":item["status"]="ABORTED";self._persist()
    def status(self,operation_id):return self.state["operations"].get(operation_id,{"status":"MISSING"})["status"]
    def committed(self):return [k for k,v in self.state["operations"].items() if v["status"]=="COMMITTED"]

class EffectAuditProtocol:
    def __init__(self,root,tool=None,log=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.journal=self.root/"effect_journal.json";self.tool=tool or IdempotentTool(self.root/"tool_operations.json");self.log=log or AuthoritativeDisclosureLog(self.root/"disclosure_log.json")
    def _journal(self,operation_id,phase,payload=None):atomic_json(self.journal,{"operation_id":operation_id,"phase":phase,"payload":payload or {}})
    def execute(self,operation_id,payload,crash_after_effect=False):
        self._journal(operation_id,"LOCAL_PREPARE",payload);self.log.prepare(operation_id);self._journal(operation_id,"AUDIT_PREPARED",payload)
        result=self.tool.execute(operation_id,payload);self._journal(operation_id,"EFFECT_CONFIRMED",payload)
        if crash_after_effect:raise CrashInjected("effect_succeeded_before_ack")
        version=self.log.commit(operation_id);self._journal(operation_id,"DONE",payload);return {**result,"audit_version":version}
    def reconcile(self):
        if not self.journal.exists():return "nothing"
        item=read_json(self.journal);op=item["operation_id"];effect=self.tool.query(op);status=self.log.status(op)
        if effect:
            if status!="COMMITTED":self.log.commit(op)
            self._journal(op,"DONE",item.get("payload"));return "committed"
        if status=="COMMITTED":raise EffectFailure("false committed audit entry")
        self.log.abort(op);self._journal(op,"ABORTED",item.get("payload"));return "aborted"

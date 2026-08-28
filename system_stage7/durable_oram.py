from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
import random
import secrets
import threading
import time
from pathlib import Path

from src.path_oram import Block,PathORAM
from system_stage6.protocol import canonical_json,seal,unseal

CRASH_POINTS=("before_path_read","after_path_read","after_stash_update","after_logical_mutation","after_leaf_remap","during_eviction","after_server_write_before_client_checkpoint","after_client_checkpoint_before_ack")

class SecurityError(RuntimeError):pass
class CrashInjected(RuntimeError):pass

def atomic_json(path,value):
    path=Path(path);tmp=path.with_suffix(path.suffix+".tmp")
    with tmp.open("wb") as f:
        f.write(canonical_json(value));f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def read_json(path):return json.loads(Path(path).read_text(encoding="utf-8"))

class IntegrityAEADSimulator:
    """Integrity/freshness simulator, explicitly not production AEAD.

    Stage-6 `seal` supplies the existing confidentiality abstraction. Standard
    HMAC-SHA-256 authenticates ciphertext and associated data. The simulator is
    used because no local AEAD library is installed.
    """
    def __init__(self,master_key,domain):self.master=master_key;self.domain=domain;self.key=hmac.new(master_key,("stage7:"+domain).encode(),hashlib.sha256).digest()
    def protect(self,payload,slot,epoch,version):
        ciphertext=seal(payload);aad={"domain":self.domain,"slot":slot,"epoch":epoch,"version":version,"ciphertext":ciphertext}
        tag=hmac.new(self.key,canonical_json(aad),hashlib.sha256).hexdigest()
        return {**aad,"tag":tag}
    def open(self,envelope,slot,epoch,version):
        try:
            if envelope["domain"]!=self.domain or envelope["slot"]!=slot or int(envelope["epoch"])!=epoch or int(envelope["version"])!=version:raise ValueError
            unsigned={k:envelope[k] for k in ("domain","slot","epoch","version","ciphertext")}
            expected=hmac.new(self.key,canonical_json(unsigned),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,envelope["tag"]):raise ValueError
            return unseal(envelope["ciphertext"])
        except Exception as exc:raise SecurityError("authenticated storage verification failed") from exc

class DurablePathORAM:
    """Copy-on-write, full-tree-checkpoint Path-ORAM feasibility prototype."""
    def __init__(self,root,n_blocks=32,seed=1,z=4,height=None,domain="storage",create=True):
        self.root=Path(root);self.trusted=self.root/"trusted";self.server=self.root/"server";self.lock=threading.RLock();self.domain=domain
        self.trusted.mkdir(parents=True,exist_ok=True);self.server.mkdir(parents=True,exist_ok=True)
        self.checkpoint_path=self.trusted/"checkpoint.json";self.keys_path=self.trusted/"keys.json";self.journal_path=self.trusted/"journal.json"
        self.last_metrics={};self.recovery_trace=[]
        if create and not self.checkpoint_path.exists():
            self.master=secrets.token_bytes(32);atomic_json(self.keys_path,{"master":base64.b64encode(self.master).decode(),"generated":"runtime-synthetic"})
            self.codec=IntegrityAEADSimulator(self.master,domain);self.oram=PathORAM(n_blocks,seed,z,height);self.epoch=1;self.txid=0;self.versions={str(i):1 for i in self.oram.tree}
            name=f"tree_{self.txid}.json";server_bytes,root_tag=self._write_server(self.server/name,self.oram,self.epoch,self.versions)
            self._write_checkpoint(name,root_tag);self.active_server_file=name;self.last_metrics={"checkpoint_bytes":self.checkpoint_path.stat().st_size,"server_bytes":server_bytes}
        else:self.recover()
    @classmethod
    def open_existing(cls,root,domain="storage"):return cls(root,domain=domain,create=False)
    def _load_key(self):
        self.master=base64.b64decode(read_json(self.keys_path)["master"]);self.codec=IntegrityAEADSimulator(self.master,self.domain)
    def _checkpoint_unsigned(self,server_file,root_tag):
        return {"domain":self.domain,"epoch":self.epoch,"txid":self.txid,"server_file":server_file,"root":root_tag,"position":{str(k):int(v) for k,v in self.oram.position.items()},"stash":[{"block_id":b.block_id,"value":b.value} for b in self.oram.stash.values()],"versions":{str(k):int(v) for k,v in self.versions.items()},"n_blocks":self.oram.n_blocks,"z":self.oram.z,"height":self.oram.height}
    def _write_checkpoint(self,server_file,root_tag):
        unsigned=self._checkpoint_unsigned(server_file,root_tag);key=hmac.new(self.master,b"stage7:checkpoint",hashlib.sha256).digest();tag=hmac.new(key,canonical_json(unsigned),hashlib.sha256).hexdigest();atomic_json(self.checkpoint_path,{**unsigned,"checkpoint_tag":tag})
    def _root(self,envelopes):
        key=hmac.new(self.master,b"stage7:trusted-root",hashlib.sha256).digest();return hmac.new(key,canonical_json(envelopes),hashlib.sha256).hexdigest()
    def _write_server(self,path,oram,epoch,versions):
        envelopes=[]
        for node in sorted(oram.tree):
            payload=[{"block_id":b.block_id,"value":b.value} for b in oram.tree[node]]
            envelopes.append(self.codec.protect(payload,f"bucket-{node}",epoch,int(versions[str(node)])))
        value={"format":"stage7-authenticated-tree-v1","envelopes":envelopes};atomic_json(path,value)
        return Path(path).stat().st_size,self._root(envelopes)
    def _verify_checkpoint(self,cp):
        unsigned={k:cp[k] for k in cp if k!="checkpoint_tag"};key=hmac.new(self.master,b"stage7:checkpoint",hashlib.sha256).digest();expected=hmac.new(key,canonical_json(unsigned),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,cp.get("checkpoint_tag","")):raise SecurityError("trusted checkpoint verification failed")
    def _load_committed(self):
        self._load_key();cp=read_json(self.checkpoint_path);self._verify_checkpoint(cp);server_path=self.server/cp["server_file"]
        try:data=read_json(server_path);envelopes=data["envelopes"]
        except Exception as exc:raise SecurityError("authenticated storage verification failed") from exc
        if self._root(envelopes)!=cp["root"] or len(envelopes)!=(1<<(int(cp["height"])+1))-1:raise SecurityError("authenticated storage verification failed")
        tree={};versions={str(k):int(v) for k,v in cp["versions"].items()}
        for node,envelope in enumerate(envelopes):
            payload=self.codec.open(envelope,f"bucket-{node}",int(cp["epoch"]),versions[str(node)])
            tree[node]=[Block(int(x["block_id"]),x["value"]) for x in payload]
        obj=PathORAM.__new__(PathORAM);obj.n_blocks=int(cp["n_blocks"]);obj.z=int(cp["z"]);obj.height=int(cp["height"]);obj.leaves=1<<obj.height;obj.rng=random.Random(int(cp["txid"])+int(cp["epoch"])*1009);obj.tree=tree;obj.position={int(k):int(v) for k,v in cp["position"].items()};obj.stash={int(x["block_id"]):Block(int(x["block_id"]),x["value"]) for x in cp["stash"]};obj.stash_samples=[];obj.max_stash=len(obj.stash)
        try:obj.assert_invariants()
        except Exception as exc:raise SecurityError("authenticated ORAM invariant failure") from exc
        self.oram=obj;self.epoch=int(cp["epoch"]);self.txid=int(cp["txid"]);self.versions=versions;self.active_server_file=cp["server_file"]
    def recover(self):
        start=time.perf_counter_ns();self._load_committed();slots=len(self.oram.tree);self.recovery_trace=[{"operation":"full_oblivious_recovery_scan","physical_slots":slots,"logical_id_visible":False}]
        for path in self.server.glob("tree_*.json"):
            if path.name!=self.active_server_file:
                try:path.unlink()
                except OSError:pass
        if self.journal_path.exists():self.journal_path.unlink()
        self.last_metrics={"recovery_ms":(time.perf_counter_ns()-start)/1e6,"recovery_bytes":(self.server/self.active_server_file).stat().st_size+self.checkpoint_path.stat().st_size,"checkpoint_bytes":self.checkpoint_path.stat().st_size,"server_bytes":(self.server/self.active_server_file).stat().st_size}
        return self
    def _crash(self,point,inject):
        if inject==point:raise CrashInjected(point)
    def access(self,block_id,operation="read",value=None,inject_crash=None):
        with self.lock:
            start=time.perf_counter_ns();old_file=self.active_server_file;next_tx=self.txid+1
            atomic_json(self.journal_path,{"txid":next_tx,"phase":"prepared","operation":operation,"opaque_target":hmac.new(self.master,str(block_id).encode(),hashlib.sha256).hexdigest()[:16]})
            working=copy.deepcopy(self.oram);self._crash("before_path_read",inject_crash)
            old_leaf=working.position[block_id];path=working.path(old_leaf)
            for node in path:
                for block in working.tree[node]:working.stash[block.block_id]=block
                working.tree[node]=[]
            self._crash("after_path_read",inject_crash);self._crash("after_stash_update",inject_crash)
            if block_id not in working.stash:raise SecurityError("authenticated ORAM invariant failure")
            prior=working.stash[block_id].value
            if operation=="write":working.stash[block_id].value=value
            elif operation!="read":raise ValueError(operation)
            self._crash("after_logical_mutation",inject_crash)
            working.position[block_id]=working.rng.randrange(working.leaves);self._crash("after_leaf_remap",inject_crash)
            working._evict(old_leaf);self._crash("during_eviction",inject_crash);working.assert_invariants()
            new_versions={k:v+1 for k,v in self.versions.items()};name=f"tree_{next_tx}.json";server_bytes,root_tag=self._write_server(self.server/name,working,self.epoch,new_versions)
            atomic_json(self.journal_path,{"txid":next_tx,"phase":"server_written","server_file":name,"root":root_tag});self._crash("after_server_write_before_client_checkpoint",inject_crash)
            self.oram=working;self.txid=next_tx;self.versions=new_versions;self._write_checkpoint(name,root_tag);self.active_server_file=name
            atomic_json(self.journal_path,{"txid":next_tx,"phase":"checkpoint_committed","server_file":name});self._crash("after_client_checkpoint_before_ack",inject_crash)
            self.journal_path.unlink(missing_ok=True)
            if old_file!=name:(self.server/old_file).unlink(missing_ok=True)
            self.last_metrics={"operation_ms":(time.perf_counter_ns()-start)/1e6,"checkpoint_bytes":self.checkpoint_path.stat().st_size,"server_bytes":server_bytes,"journal_bytes_written":len(canonical_json({"txid":next_tx,"phase":"prepared"})),"path_blocks":2*len(path)*working.z}
            return prior,{"physical_path":path,"logical_id_visible":False,"checkpoint_operation":"full_tree_cow"}
    def peek(self,block_id):
        if block_id in self.oram.stash:return self.oram.stash[block_id].value
        for bucket in self.oram.tree.values():
            for block in bucket:
                if block.block_id==block_id:return block.value
        raise SecurityError("authenticated ORAM invariant failure")
    def rotate_key(self):
        with self.lock:
            old_file=self.active_server_file;self.master=secrets.token_bytes(32);atomic_json(self.keys_path,{"master":base64.b64encode(self.master).decode(),"generated":"runtime-synthetic-rotated"});self.codec=IntegrityAEADSimulator(self.master,self.domain);self.epoch+=1;self.txid+=1;self.versions={k:v+1 for k,v in self.versions.items()};name=f"tree_{self.txid}.json";server_bytes,root_tag=self._write_server(self.server/name,self.oram,self.epoch,self.versions);self._write_checkpoint(name,root_tag);self.active_server_file=name;(self.server/old_file).unlink(missing_ok=True);return server_bytes
    def durable_sizes(self):
        return {"key_bytes":32,"position_map_bytes":len(self.oram.position)*4,"stash_bytes":len(canonical_json([{"id":b.block_id,"value":b.value} for b in self.oram.stash.values()])),"epoch_version_bytes":8+4*len(self.versions),"checkpoint_bytes":self.checkpoint_path.stat().st_size,"journal_bytes":self.journal_path.stat().st_size if self.journal_path.exists() else 0,"server_bytes":(self.server/self.active_server_file).stat().st_size}
    def active_server_bytes(self):return (self.server/self.active_server_file).read_bytes()
    def replace_active_server_bytes(self,data):(self.server/self.active_server_file).write_bytes(data)

class ORAMCoordinator:
    """Single trusted serialization point for one authoritative ORAM domain."""
    def __init__(self,oram):self.oram=oram;self.lock=threading.Lock();self.wait_samples=[];self.service_samples=[]
    def access(self,*args,**kwargs):
        started=time.perf_counter_ns()
        with self.lock:
            acquired=time.perf_counter_ns();result=self.oram.access(*args,**kwargs);ended=time.perf_counter_ns()
        wait=(acquired-started)/1e6;service=(ended-acquired)/1e6;self.wait_samples.append(wait);self.service_samples.append(service)
        return result,{"coordination_wait_ms":wait,"serialization_ms":service}

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import socket
import struct
import time
from dataclasses import dataclass

SYNTHETIC_KEY=b"stage6-local-synthetic-protection-key"

def canonical_json(value):
    return json.dumps(value,separators=(",",":"),sort_keys=True).encode("utf-8")

def _keystream(n):
    out=b"";counter=0
    while len(out)<n:
        out+=hashlib.sha256(SYNTHETIC_KEY+counter.to_bytes(4,"big")).digest();counter+=1
    return out[:n]

def seal(value):
    raw=canonical_json(value);stream=_keystream(len(raw))
    return base64.b64encode(bytes(a^b for a,b in zip(raw,stream))).decode("ascii")

def unseal(value):
    raw=base64.b64decode(value);stream=_keystream(len(raw))
    return json.loads(bytes(a^b for a,b in zip(raw,stream)).decode("utf-8"))

def opaque_token(kind,value):
    return hmac.new(SYNTHETIC_KEY,f"{kind}:{value}".encode(),hashlib.sha256).hexdigest()[:20]

def branch_label(request_id):
    return hashlib.sha256(("branch:"+request_id).encode()).digest()[0]&1

def recv_exact(sock,n):
    out=b""
    while len(out)<n:
        part=sock.recv(n-len(out))
        if not part:raise ConnectionError("unexpected EOF")
        out+=part
    return out

def send_frame(sock,obj):
    raw=canonical_json(obj);sock.sendall(struct.pack("!I",len(raw))+raw);return len(raw)+4

def recv_frame(sock):
    size=struct.unpack("!I",recv_exact(sock,4))[0];raw=recv_exact(sock,size)
    return json.loads(raw.decode("utf-8")),size+4

@dataclass
class RpcResult:
    response:dict
    request_bytes:int
    response_bytes:int
    duration_ms:float
    wall_start_ns:int
    wall_end_ns:int

def rpc(port,message,timeout=15):
    start=time.perf_counter_ns();wall_start=time.time_ns()
    with socket.create_connection(("127.0.0.1",port),timeout=timeout) as sock:
        request_bytes=send_frame(sock,message);response,response_bytes=recv_frame(sock)
    wall_end=time.time_ns()
    return RpcResult(response,request_bytes,response_bytes,(time.perf_counter_ns()-start)/1e6,wall_start,wall_end)

def reserve_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1",0));return s.getsockname()[1]

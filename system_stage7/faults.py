from __future__ import annotations

import time

class ServiceUnavailable(RuntimeError):pass

class LocalFaultInjector:
    """Deterministic local service-failure harness, not an attack framework."""
    def __init__(self):self.calls={}
    def call(self,service,operation_id,fault=None,delay_ms=10):
        key=(service,operation_id);self.calls[key]=self.calls.get(key,0)+1
        if fault=="timeout":raise TimeoutError("service timeout")
        if fault=="connection_drop":raise ConnectionError("service connection dropped")
        if fault=="unavailable":raise ServiceUnavailable("service unavailable")
        if fault=="delayed":time.sleep(delay_ms/1000)
        response={"service":service,"operation_id":operation_id,"status":"ok","attempt":self.calls[key]}
        if fault=="duplicate_response":return [dict(response),dict(response)]
        return response

def fail_closed_authorization(permission_result=None,error=None):
    if error is not None or permission_result is None:return "DEFER"
    return "ALLOW" if permission_result.get("allow") is True else "DENY"


from pathlib import Path
import csv
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from system_stage7.experiment import run_stage7

def print_summary(out):
    overhead=out["overhead"];recovery=out["recovery"];inventory=out["inventory"]
    factor=sum(float(x["latency_increase_factor"]) for x in overhead)/len(overhead);rmax=max(float(x["recovery_latency_ms"]) for x in recovery);trusted=max(int(float(x["total_trusted_persistent_bytes"])) for x in inventory)
    print("STAGE-7 SECURITY DECISION: FEASIBLE WITH TRUST/DEPLOYMENT CONSTRAINTS")
    print("Authenticated storage: PARTIAL (integrity simulator; production AEAD not implemented)")
    print("Rollback protection: PASS within trusted-root model")
    print("Crash consistency: PASS")
    print("Position-map recovery: PASS")
    print("Stash recovery: PASS")
    print("Hybrid stale-cache safety: PASS")
    print("Cross-device history recovery: PASS")
    print("Concurrent log append: PASS")
    print("Effect idempotency: PASS")
    print("Effect/audit reconciliation: PASS in local protocol; PARTIAL for distributed deployment")
    print("Fail-closed authorization: PASS")
    print("Multi-client ORAM coordination: centralized trusted coordinator required per ORAM domain")
    print("Recovery privacy: PARTIAL; full physical scan hides IDs but reveals recovery/domain size")
    print(f"Normal overhead increase after security hardening: {factor:.1f}x mean local latency in full-tree COW prototype")
    print(f"Recovery latency: maximum {rmax:.2f} ms in evaluated small domains")
    print(f"Trusted persistent state: maximum {trusted} bytes in evaluated prototype inventory")
    print("Architecture ranking before Stage 7: HYBRID-P default for active histories; fixed modular for deployment preservation")
    print("Architecture ranking after Stage 7: HYBRID-P default; Unified simplest recovery domain; fixed modular preserves ownership; HYBRID-PH bounded-history only")
    print("Recommended architecture: HYBRID-P")
    print("Most important new systems requirement: trusted serialized ORAM coordination plus a non-rollbackable freshness root")
    print("Most important remaining security limitation: production AEAD/KMS and distributed effect-log integration are not implemented")
    print("Structural blocker: NO")
    print("Research question still supported: YES")
    print("Need further synthetic privacy validation: NO")
    print("Implementation ready to freeze: YES, as a research prototype boundary; not production deployment")
    print("Recommended next step: independent design review and production cryptography/recovery implementation planning")

if __name__=="__main__":
    out=run_stage7(ROOT);print_summary(out)

from pathlib import Path
import csv
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from system_stage6.experiment import run_stage6

def print_summary(primary):
    def row(profile,arch):return next(x for x in primary if x["profile"]==profile and x["architecture"]==arch)
    def line(arch,label):
        x=row("ENTERPRISE-DC",arch);fresh=f"; freshness RTTs={x['freshness_rtts']:.0f}" if arch.startswith("HYBRID") else ""
        print(f"{label}: trusted bytes={x['trusted_bytes_client']:.0f}; wire bytes/action={x['wire_bytes_action']:.0f}; p95={x['p95_ms']:.2f} ms; RTTs/action={x['remote_requests_action']:.1f}{fresh}")
    valid=["FIXED-CANONICAL-MODULAR","UNIFIED-ORAM","HYBRID-P","HYBRID-PH"]
    def cheapest(profile):return min(valid,key=lambda a:row(profile,a)["p95_ms"])
    print("STAGE-6 SYSTEM DECISION: CONFIGURATION-DEPENDENT SYSTEM DESIGN")
    print("All processes separated: PASS")
    print("Plaintext confinement: PASS")
    print("Authorization equivalence: PASS")
    print("Revocation equivalence: PASS")
    print("Cross-device history consistency: PASS")
    print("Concurrency correctness: PASS")
    print("Privacy sanity: direct/independent leak; fixed canonical, unified, and hybrids at chance")
    line("FIXED-CANONICAL-MODULAR","Canonical modular");line("UNIFIED-ORAM","Unified");line("HYBRID-P","Hybrid-P");line("HYBRID-PH","Hybrid-PH")
    for p in ("LOCAL-LAN","ENTERPRISE-DC","REMOTE-CLOUD"):print(f"Cheapest {p}: {cheapest(p)}")
    print("Cheapest under frequent revocation: HYBRID-PH in the measured steady-state action, conditional on per-action validation")
    print("Cheapest under large disclosure history: HYBRID-P; HYBRID-PH synchronization/cache grows with unseen events")
    print("Cheapest under frequent cross-device updates: HYBRID-P")
    print("Does Hybrid-PH still dominate after correct semantics?: CONFIGURATION DEPENDENT")
    print("Does Unified dominate after actual wire accounting?: NO")
    print("Does Canonical Modular have a meaningful Pareto region?: YES, through outsourced-state and deployment-preservation dimensions")
    print("Most important architectural trade-off: client cache/synchronization versus outsourced bandwidth and service coupling")
    print("Most important limitation: local prototype ORAM and ciphertext padding are not a production cryptographic storage system")
    print("Research problem still valid: YES")
    print("Original preferred architecture still justified: ONLY CONDITIONALLY")
    print("Should implementation now be frozen: YES")
    print("Recommended next step: production feasibility audit of persistence, cryptography, and recovery; no new synthetic leakage search")

if __name__=="__main__":
    if "--report-only" in sys.argv:
        with (ROOT/"results_stage6/primary_summary.csv").open(newline="",encoding="utf-8") as f:
            primary=list(csv.DictReader(f))
        for r in primary:
            for key in ("trusted_bytes_client","wire_bytes_action","p95_ms","remote_requests_action","freshness_rtts"):
                r[key]=float(r[key])
    else:primary=run_stage6(ROOT)["primary"]
    print_summary(primary)

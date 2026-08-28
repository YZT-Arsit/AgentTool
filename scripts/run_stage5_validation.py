from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.stage5 import ARCHS,REGIMES,run_stage5
if __name__=="__main__":
    privacy,costs,measured,memory=run_stage5(ROOT)
    def c(reg,a):return next(x for x in costs if x["regime"]==reg and x["architecture"]==a)
    def p(a,k):z=[float(x[k]) for x in measured if x["architecture"]==a];return sum(z)/len(z)
    def cheapest(reg):return min((x for x in costs if x["regime"]==reg and x["privacy"]=="pass" and float(x["trusted_state_bytes"])<=16*1048576),key=lambda x:float(x["bytes_action"]))["architecture"]
    print("STAGE-5 TRADE-OFF DECISION: CONFIGURATION-DEPENDENT PARETO FRONTIER")
    print("Privacy-equivalent architectures: "+", ".join(a for a in ARCHS if a not in ("MODULAR-ORAM","RANDOMIZED-PARTITION")))
    for r,name in (("S","small"),("M","medium"),("L","large"),("H","heterogeneous")):print(f"Cheapest architecture in {name} regime: {cheapest(r)}")
    for a,label in (("CANONICAL-MODULAR","Canonical modular"),("NAIVE-FIXED","Naive fixed modular"),("UNIFIED-FIXED","Unified"),("UNIFIED-PACKED","Unified packed"),("RANDOMIZED-PARTITION","Randomized partition"),("HYBRID-P","Hybrid-P"),("HYBRID-PH","Hybrid-PH")):
        x=c("M",a);print(f"{label}: bytes/action={float(x['bytes_action']):.0f}; p95={p(a,'p95_latency_us'):.1f} us; trusted memory={float(x['trusted_state_bytes']):.0f}")
    print("Fixed-scan crossover: at 128 B/record, scan wins through 128/64/32 records for LOCAL/DATACENTER/REMOTE profiles")
    print("Does canonical beat naive fixed?: NO; identical schedule and analytical cost")
    print("Does unified dominate canonical?: NO; depends on packing and store/record heterogeneity")
    print("Does randomized partitioning dominate either?: NOT IMPLEMENTED; functional remap abstraction excluded from privacy-equivalent set")
    print("Does trusted-state hybrid dominate for small state?: YES when permission/history fit the stated trusted-memory budget")
    print("Most important crossover: history growth moves HYBRID-PH from minimal I/O to excessive trusted memory")
    print("Most important fairness caveat: partition and packing costs are conservative models, not production protocol implementations")
    print("Recommended architecture: HYBRID-PH when its persistence and trusted-memory costs are acceptable; otherwise select canonical modular or unified unpadded by workload")
    print("Is the current architecture contribution still justified?: ONLY AS A PARETO DESIGN POINT")
    print("Should the empirical trade-off now be frozen?: YES")

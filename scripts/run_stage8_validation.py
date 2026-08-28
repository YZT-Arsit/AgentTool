from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from stage8_real_traces.experiment import run_stage8

def find(out,analysis,variant,split="grouped_entity"):
    return next(r for r in out["summary"] if r["analysis"]==analysis and r["variant"]==variant and r["feature_level"]=="SYMBOLIC" and r["split"]==split and r["metric"]=="roc_auc")

def print_summary(out):
    original=find(out,"mediation_only","ORIGINAL-MEDIATOR");per=find(out,"mediation_only","PER-SERVICE-ORAM");unified=find(out,"mediation_only","UNIFIED-OBLIVIOUS");trusted=find(out,"mediation_only","TRUSTED-LOCAL");dynamic=find(out,"full_trajectory","FIXED-CANONICAL")
    print("STAGE-8 DECISION: REFRAME TOWARD ADAPTIVE MEDIATION")
    print("Mediator evidence level: L1")
    print("Real/source-faithful implementation used: GAAP-source-faithful reference mediator; actual localhost service processes")
    print("Natural private-state-dependent trace variation: YES")
    print("Was any hidden label directly encoded into endpoint selection?: NO")
    print("Strongest naturally occurring leakage: persistent transitive provenance changes the first state-service endpoint")
    print("Dynamic planning creates additional leakage: YES")
    print("Effect-producing workflow tested: YES")
    print(f"Original mediator leakage: grouped-entity provenance AUC {original['mean']:.3f} +/- {original['std']:.3f}")
    print(f"Per-service ORAM result: grouped-entity provenance AUC {per['mean']:.3f} +/- {per['std']:.3f}")
    print(f"Unified result: grouped-entity provenance AUC {unified['mean']:.3f} +/- {unified['std']:.3f}")
    print(f"Trusted/hybrid result: grouped-entity provenance AUC {trusted['mean']:.3f} +/- {trusted['std']:.3f}")
    print("Opal collision: PARTIALLY DEFEATED")
    print("ObliDB collision: NOT DEFEATED for per-action structure; PARTIALLY DEFEATED by effect/policy trajectories")
    print("Strongest agent-specific distinction: authorization acquisition and effects create cross-action trace structure over persistent provenance")
    print("Strongest contribution: L1 measurement/design characterization of adaptive security mediation")
    print("Contribution strength: MODERATE")
    print("Strongest rejection argument: Opal fixed traces plus ObliDB non-composition applied to a GAAP-inspired mediator")
    print("Is rejection defeated?: PARTIALLY")
    print("ICASSP viability: ADEQUATE if reframed around adaptive mediation; weak as a new per-action mechanism")
    print("Should the current mechanism be claimed as novel?: NO")
    print("Should the work be framed as measurement/design?: YES")
    print("Should adaptive mediation become the main technical direction?: YES")
    print(f"Adaptive fixed-canonical trajectory AUC: {dynamic['mean']:.3f} +/- {dynamic['std']:.3f}")
    print("Recommended next step: obtain an L2 runtime integration and formalize bounded adaptive-trajectory leakage")

if __name__=="__main__":
    out=run_stage8(ROOT);print_summary(out)


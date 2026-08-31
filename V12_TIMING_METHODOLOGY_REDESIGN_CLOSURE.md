# V12 Timing Methodology Redesign Closure

This is an execution-free protocol freeze. It does not select a profile,
calculate protected AUCs, or authorize confirmatory/final work.

## Task definitions

All pairs hold the public profile, framework, block, semantic arguments, and
effect semantics fixed unless the named estimand necessarily includes one of
those private mechanisms. Both frameworks receive independent pairs.

| Task | Changed factor | Additional fixed factors | Expected private runtime difference | Observer | Status |
|---|---|---|---|---|---|
| T1 | reusable descriptor vs legitimate re-resolution | same Agent/action sequence required | cache hit vs real resolution | Registry | NOT_FEASIBLE under frozen semantics |
| T2 | private Agent identity | action names/count | descriptor/cache selection | Registry, Relay | ISOLATED |
| T3 | private Tool/action identity | Agent identity/count | private dispatch | Relay | ISOLATED |
| T4 | repeated vs distinct targets | count/action family | target reuse | Relay | ISOLATED |
| T5 | common vs one predeclared rare target | count/action family | one target identity | Relay | ISOLATED |
| T6 | transition order | action multiset/count | order only | Relay | ISOLATED |
| T7 | Tool vs Agent-as-Tool | count | action family plus descriptor/dispatch | Registry, Relay | COMPOSITE |
| T8 | trusted-local vs external mediated | count | placement plus route/action mechanism | Registry, Relay | COMPOSITE |
| T9 | early vs late-ready-within-bound | identity/count | provider completion timing | Relay | ISOLATED |
| T10 | causal depth/count | public profile | count, depth, private work volume | Relay | COMPOSITE |

Every pair requires equality of `H`, `Delta`, `R`, request/response sizes,
`Q`, PIR epoch/period, OHTTP suite, connection policy, public framework
iteration limits, `M`, and session count. A pair with unequal public profile
signatures is rejected.

## Train/evaluation protocol

For each profile/task/framework coordinate, hash-sort complete block IDs before
execution and assign 60% to DEVELOPMENT_TRAIN and 40% to DEVELOPMENT_EVAL.
Both pair members remain together. Feature selection, normalization, fitting,
and hyperparameters use TRAIN only.

The four frozen model families are logistic regression, Extra Trees,
histogram gradient boosting, and RBF SVM. EVAL produces four fixed prediction
vectors. `FAMILY_AUC` is their maximum. Each of 10,000 bootstrap replicates
resamples complete EVAL pairs, computes all four AUCs, and takes their maximum.
There is no refit inside the EVAL bootstrap. A secondary randomization test may
independently swap labels within each complete pair only.

## Positive controls

The Registry control is the owned local no-cover descriptor-resolution mode;
the Relay control is the owned local unshaped/direct mode. Future controls must
reuse the same task, framework, split, classifier family, and feature contract.
They were not executed in this closure.

## Preserved runtime

No scheduler, pacer, Gateway, PIR, framework adapter, provider semantic,
`H`, Delta, PIR schedule, `Q`, `M`, or public transcript runtime code was
changed by this closure. The selected functional state remains an input fact,
not a result rerun here.

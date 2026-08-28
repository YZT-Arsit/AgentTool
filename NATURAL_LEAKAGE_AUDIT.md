# Stage-8 Natural Leakage Audit

## Natural semantic variables

Two independently sampled private properties were evaluated:

1. **Persistent transitive provenance:** whether the value used by an authorized
   effect comes directly from the private-data DB or carries a persistent taint
   recovered from the disclosure log.
2. **Missing permission:** whether the current data-item/party pair lacks a
   permission and therefore requires consent, persistence, and retry.

Neither is an arbitrary class. Enterprise state is sampled before a task; labels
are derived after execution.

## Mediation-only symbolic result

Analysis conditions on an existing ALLOW permission, one public action, and
SEND_MESSAGE/SHARE_DOCUMENT. Both classes execute four host events in Original
and Per-service ORAM. The difference is the naturally selected first service:

```text
direct:      PRIVATE_DATA_DB -> PERMISSION_DB -> TOOL -> DISCLOSURE_LOG
transitive:  DISCLOSURE_LOG  -> PERMISSION_DB -> TOOL -> DISCLOSURE_LOG
```

The endpoint-sequence sets are disjoint (Jaccard 0). Per-service ORAM replaces
the logical operation/address with a randomized path but retains this endpoint
difference. Unified, fixed-canonical, and trusted-local have identical sequence
sets (Jaccard 1) for the two provenance classes.

| Variant | Grouped-entity AUC | Cross-policy AUC | SEND→SHARE AUC | Symbolically distinct? |
|---|---:|---:|---:|---|
| Original mediator | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | yes |
| Per-service ORAM | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | yes |
| Unified oblivious | 0.449 ± 0.095 | 0.444 ± 0.008 | 0.500 ± 0.000 | no |
| Fixed canonical | 0.449 ± 0.095 | 0.444 ± 0.008 | 0.500 ± 0.000 | no |
| Trusted local | 0.449 ± 0.095 | 0.444 ± 0.008 | 0.500 ± 0.000 | no |

Protected-variant grouped/cross-policy fluctuations are not evidence of leakage:
the symbolic traces are exactly identical by construction, the classifier has
no discriminating endpoint/operation feature, and permutation controls are in
the same finite-sample range. Cross-task AUC is exactly 0.5.

## Adaptive trajectory result

The stronger natural distinction compares an existing ALLOW with MISSING policy
followed by ALLOW consent. Both end with exactly one effect. Missing policy
causes actual consent acquisition, policy persistence, and a second mediated
attempt. Mean class trace lengths are:

| Variant | Existing ALLOW | Missing→ALLOW | Grouped-entity AUC | Permutation AUC |
|---|---:|---:|---:|---:|
| Original mediator | 4 | 8 | 1.000 | 0.519 |
| Per-service ORAM | 4 | 8 | 1.000 | 0.514 |
| Unified oblivious | 4 | 8 | 1.000 | 0.506 |
| Fixed canonical | 6 | 12 | 1.000 | 0.510 |
| Trusted local | 1 | 2 | 1.000 | 0.517 |

This is a deterministic symbolic distinction; ML adds no sophistication. It
shows that per-action state-trace protection does not hide adaptive continuation,
user interaction, or retry. It does not show that action count or effect
occurrence was promised private by GAAP or Opal.

## Raw evidence and overhead

The run captured 21,535 actual localhost RPC events from 4,800 variant executions
over 960 state/task episodes and three seeds. All 4,800 outputs matched Original.
Mean events per episode were 4.60 Original/Per-service/Unified, 7.66 Fixed, and
0.96 Trusted-local. Mean observed RPC duration was 46.3/47.4/47.4/78.2/9.7 ms;
these Windows localhost timings are trace realism evidence, not a systems
benchmark.

## Interpretation

The per-action result is a valid L1 measurement but its principle collides with
ObliDB's end-to-end non-composition observation. The adaptive result is more
agent-specific because it couples persistent authorization acquisition,
effect-producing tool calls, disclosure provenance, and subsequent planning;
it is still an open characterization/design problem, not a new obliviousness
primitive.

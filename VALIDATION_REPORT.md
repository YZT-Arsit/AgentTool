# Validation Report: Execution-Plane Mediation-Trace Privacy

## 1. Question

This experiment tested whether host-visible persistent-state access metadata can
reveal private binding state after plaintext content has been hidden, and
whether a schema-compiled, canonical ORAM-style mediation trace suppresses the
remaining signal. The result is **SUPPORTED** within the stated synthetic model.

## 2. Threat model

The trusted components are the synthetic user, mediator, simulator internals,
and ORAM client state. An honest-but-curious host sees each persistent access's
store, operation, order, and either a stable opaque address (V0/V1) or a
randomized ORAM path (V2/V3). It sees the public action type and episode
boundary. It cannot see plaintext, logical handles, dummy status, mediator
memory, or private labels. External network destinations, external tools,
malicious providers, full trajectories, TEEs, and real authorization systems
are outside scope. Every primary episode is `SEND_MESSAGE`, so no probe predicts
the intentionally public action family.

## 3. Simulator

The environment is fully offline and synthetic. It defines `SEND_MESSAGE`,
`SHARE_FILE`, `CREATE_EVENT`, and `BOOK_TRAVEL` schemas and evaluates 6,000
balanced `SEND_MESSAGE` episodes for each of seeds 0, 1, and 2. Episodes vary 16
recipients, 32 possible documents, explicit versus implicit selection among four
accounts, two policy states, and an independently sampled history-relevance bit.
Concrete values use only reserved/synthetic forms such as
`person7@example.invalid` and `synthetic_account_2`.

Four occupancy classes (recipient only, attachment, explicit account, and both)
are exactly balanced. Recipient, document, policy, and history values are
sampled independently except for the ordinary default-account rule
`recipient mod 4`. No correlation was added to improve classifier performance.
Ground truth is held in `Action` objects and never serialized into host traces.

The inference fallback is a standard-library multinomial Naive Bayes classifier
over trace length, per-store counts, ordered store/operation positions,
bigrams, stable address tokens, and visible ORAM paths. It uses a fixed 70/30
train/test split. These simple features are deliberately interpretable.

## 4. Variants

- **V0 — direct/capability-only:** stable HMAC-like pseudonymous record tokens;
  plaintext never appears in the trace.
- **V1 — encrypted direct storage:** payload confidentiality is abstracted, but
  the stable opaque storage location remains visible. Heavyweight cryptography
  is unnecessary because payload content is not an experimental variable.
- **V2 — ORAM-style, unshaped:** every logical access emits a uniformly sampled
  six-node root-to-leaf path. Logical identity is remapped after every access in
  the intended model, while optional dependencies are omitted.
- **V3 — canonical schema-driven:** `compile_schema` produces a fixed nine-access
  schedule for `SEND_MESSAGE`. Every slot emits the same ORAM trace abstraction;
  unused slots have no visible dummy marker.

The ORAM component is explicitly a trace-only idealization, not a production
Path ORAM. It does not model block encryption/movement, stash bounds, eviction,
concurrency, failures, or implementation side channels.

## 5. Inference probes

- **A:** predict one of 16 recipient identities, restricted to the fixed “both
  optional fields present” occupancy class.
- **B:** predict whether a balanced pair of episodes used the same recipient.
- **C:** predict one of the four optional-field occupancy patterns.
- **D:** predict the independent private history-relevance bit, which causes an
  optional history read in V0–V2.

All features come exclusively from host-visible traces. Shuffled-label controls
use the identical inference pipeline.

## 6. Results

Values are test-set mean ± population standard deviation across three seeds.
The shuffled column reports the corresponding primary metric (accuracy for
multiclass; ROC-AUC for linkability/history).

| Probe / metric | Chance | V0 | V1 | V2 | V3 |
|---|---:|---:|---:|---:|---:|
| A recipient accuracy | 0.0625 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.064 ± 0.016 | 0.064 ± 0.016 |
| A recipient macro-F1 | 0.0625 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.060 ± 0.017 | 0.062 ± 0.016 |
| B linkability ROC-AUC | 0.500 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.513 ± 0.015 | 0.496 ± 0.006 |
| B linkability accuracy | 0.500 | 0.989 ± 0.006 | 0.989 ± 0.006 | 0.509 ± 0.012 | 0.498 ± 0.009 |
| C occupancy accuracy | 0.250 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.257 ± 0.006 |
| C occupancy macro-F1 | 0.250 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.256 ± 0.006 |
| D history ROC-AUC | 0.500 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.502 ± 0.009 |
| D history accuracy | 0.500 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.502 ± 0.004 |

Representative shuffled-label baselines were 0.064 ± 0.022 for V0 recipient
accuracy, 0.254 ± 0.004 for V2 occupancy accuracy, 0.251 ± 0.005 for V3
occupancy accuracy, 0.490 ± 0.016 for V2 linkability AUC, and 0.499 ± 0.011
for V3 history AUC. The complete controls are in `results/summary.csv`.

Thus H1 is supported: encrypting payloads while retaining stable addresses did
not reduce identity or linkability. H2 is supported: V2 eliminated address-based
identity and linkage but retained mediation-shape leakage. H3 is supported in
this workload: V3 performance closely tracked chance and shuffled controls. H4
is supported by exhaustive generated-action equivalence tests.

## 7. Leakage source analysis

The V2 occupancy ablation isolates the residual source:

| Host observation | Accuracy | Chance | Shuffled mean |
|---|---:|---:|---:|
| Access count only | 0.629 ± 0.018 | 0.250 | 0.249 |
| Count + store type | 1.000 ± 0.000 | 0.250 | 0.253 |
| Count + store + ordering | 1.000 ± 0.000 | 0.250 | 0.256 |
| Full visible ORAM trace | 1.000 ± 0.000 | 0.250 | 0.254 |

Counts partially identify occupancy but collide because the independent history
read can add one access. Per-store counts resolve the collision: attachment and
explicit-account dependencies touch distinct store categories. Ordering and
random ORAM paths add no further measured benefit. In V0/V1, stable addresses
are the source of recipient identity and repetition/linkability leakage. V3
removes variable counts, store shape, and ordering for a fixed public schema.

## 8. Functional correctness

`test_all_mediation_variants_are_functionally_equivalent` compared all concrete
tool arguments for 200 generated actions and passed. The suite also passed
explicit host/private separation, well-formed ORAM path, constant V3 length,
constant V3 store/operation shape, and absence-of-dummy-marker tests. Overall:
4 tests passed.

## 9. Overhead

| Variant | Mean visible accesses/action | Mean path events/action | Mean mediation time (µs/action) |
|---|---:|---:|---:|
| V0 | 7.005 | 7.005 | 25.98 |
| V1 | 7.005 | 7.005 | 25.76 |
| V2 | 7.005 | 42.03 | 20.60 |
| V3 | 9.000 | 54.00 | 29.39 |

V3 uses 1.285× the visible accesses of V2 and 1.285× those of V0 for this
workload. Counting six bucket events per simulated path, V2 and V3 have roughly
6× path-event bandwidth relative to an ordinary direct access; V3 has 1.285×
V2's path-event bandwidth. Microbenchmarks are Python-level and noisy (including
warm-up/runtime effects), so access and path-event ratios are more meaningful
than absolute latency.

## 10. Research conclusion

**SUPPORTED**

Both required decision criteria are met. Content-protected direct mediation
exposes strong private identity and linkability signals through stable opaque
addresses. After idealized address hiding, V2 still exposes independently
sampled private occupancy and history state through variable cross-store access
shape; V3 reduces those probes from 1.000 to 0.257 occupancy accuracy and from
1.000 to 0.502 history AUC while preserving identical functional semantics.

This conclusion is deliberately narrow. The experiment establishes feasibility
and a clean synthetic counterexample to “address obliviousness implies complete
mediation-trace privacy.” It does not establish real-system effect size,
production ORAM security, literature novelty, or protection from side channels
outside the stated host-visible persistent-state boundary.

## 11. Implications for a short paper

The data justify the following bounded claim: content confidentiality and
logical-address hiding do not necessarily eliminate execution-plane leakage
from synthetic agent tool mediation. Data-dependent accesses across private
objects, authorization state, credentials, and persistent history can reveal
hidden binding structure. A schema-derived canonical schedule suppresses that
signal in the evaluated workload, at the cost of padded accesses and additional
ORAM path bandwidth.

A credible next step is to reproduce the experiment in a real mediator with a
complete ORAM library, multiple public schemas, realistic correlated workloads,
stronger sequence classifiers, explicit leakage-class definitions, confidence
intervals, and end-to-end latency/bandwidth measurements.

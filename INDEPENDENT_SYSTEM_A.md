# Independent System A: GAAP-derived

## System/source

The source is *An AI Agent Execution Environment to Safeguard User Data*
(arXiv:2604.19657v1). Stage 4 derives only the paper's private-data, permission,
and disclosure-log dependencies. It does not reproduce GAAP.

## Architecture summary and trust

GAAP confines private values from the untrusted model, runs a code artifact in a
trusted execution environment, tracks private-data flow, intercepts external
tool calls, consults user disclosure permissions, and maintains a disclosure log
across calls/tasks. The local experiment trusts mediator/ORAM client state and
exposes only server-side Path-ORAM traces.

## Architecture-fidelity table

| Component/access | Confidence | Reason | Local abstraction |
|---|---|---|---|
| Private-data lookup | DOCUMENTED | Private-data DB API accesses values by key | `PRIVATE_DATA_DB` |
| Permission lookup | DOCUMENTED | DB queried for data keys and external party before disclosure | `PERMISSION_DB` |
| Credential lookup | NOT SUPPORTED | Not required by the selected disclosure workflow | not implemented |
| Provenance/history read | DOCUMENTED | Disclosure log queried for indirect/transitive taints | `DISCLOSURE_LOG` read |
| Disclosure record | DOCUMENTED | New entry added for every private disclosure | `DISCLOSURE_LOG` write |
| Authorization decision | DOCUMENTED | IFC/permission enforcement before MCP call | trusted Boolean compute |
| Tool invocation | DOCUMENTED | Environment intercepts MCP calls | offline mock send |

## Source, deployment, and experiment separation

- **Source-derived:** the three DB roles and direct/transitive disclosure steps.
- **Deployment assumption:** each DB is a separate host-distinguishable ORAM
  endpoint.
- **Experiment abstraction:** equal-size synthetic records, a local mock message
  sink, and direct-versus-transitive data origin as the hidden state.

## Derived workflow and hidden state

For a direct private value, the mediator reads `PRIVATE_DATA_DB`, checks
`PERMISSION_DB`, calls the mock sink, and writes `DISCLOSURE_LOG`. For an API
value potentially carrying prior private data, the mediator reads
`DISCLOSURE_LOG` to recover transitive taint, checks the same permission DB, and
writes the new disclosure. Both use three accesses and the same read/read/write
histogram. The hidden dimension is direct versus transitive private origin.

The pre-classification audit found equal total count, different modular store
histogram, different first endpoint, and identical operation sequence.

## Privacy results

Balanced F4 results across three seeds:

| Variant | Accuracy | Macro-F1 | ROC-AUC | Permutation accuracy |
|---|---:|---:|---:|---:|
| MODULAR-ORAM | 1.000 ± .000 | 1.000 ± .000 | 1.000 ± .000 | .509 ± .021 |
| CANONICAL-MODULAR | .474 ± .012 | .322 ± .006 | .500 ± .000 | .502 ± .009 |
| UNIFIED-ORAM | .474 ± .012 | .322 ± .006 | .500 ± .000 | .502 ± .009 |
| UNIFIED-ORAM-PAD | .474 ± .012 | .322 ± .006 | .500 ± .000 | .502 ± .009 |

The below-.5 accuracy/F1 occurs because an invariant-feature Naive Bayes model
selects one class and each test fold is slightly imbalanced. ROC-AUC is exactly
.500 and is the appropriate invariant-signal diagnostic. F0 count is at chance;
F1 store histogram is the first perfect feature. Grouped-entity F4 remains 1.000
for modular and approximately .512 for protected variants.

At the natural 70/30 mixture, modular accuracy/macro-F1/AUC remain 1.000; other
variants have .500 AUC and their accuracy matches the roughly .70 majority/
permutation baseline.

## Performance

| Variant | Logical | Physical blocks | Bandwidth | Mean/p50/p95 µs | Mean/max stash | Dummy fraction |
|---|---:|---:|---:|---:|---:|---:|
| MODULAR-ORAM | 3 | 276 | 1.078 MiB | 242.1/232.7/339.5 | .018/5 | 0 |
| CANONICAL-MODULAR | 4 | 368 | 1.438 MiB | 292.9/279.7/401.6 | .009/6 | .250 |
| UNIFIED-ORAM | 3 | 312 | 1.219 MiB | 342.0/329.4/488.0 | .017/5 | 0 |
| UNIFIED-ORAM-PAD | 4 | 416 | 1.625 MiB | 414.4/397.6/582.0 | .008/4 | .250 |

Canonical modular is cheaper than unified padded but transfers more than
unpadded unified, which already hides this equal-work channel. No universal
canonical cost advantage is claimed.

## Correctness and limitations

Functional and authorization equivalence pass for allowed and denied cases.
The result is **POSITIVE WITH A MATERIAL DEPLOYMENT ASSUMPTION**. It shows that
GAAP's documented heterogeneous state dependencies can leak when deployed as
separately observable ORAM services. It does not demonstrate leakage in GAAP's
actual prototype or prove the paper uses such a deployment.

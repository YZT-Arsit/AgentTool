# Legacy deprecation manifest V6

| Path/family | V6 classification | Handling |
|---|---|---|
| `agent_control_virtualization/` | HISTORICAL / OPTIONAL SANDBOX RESEARCH | preserved, no canonical import |
| `canonical_v3/` | HISTORICAL IR-based integration | preserved, no canonical import |
| `semantic_fidelity/` and IR holdouts | HISTORICAL EVIDENCE | frozen results retained |
| `confidential_v5/attestation.py` | REUSED BOOTSTRAP DEPENDENCY | only cryptographic session bootstrap reused; no Control IR |
| other `confidential_v5` Control Kernel/resolution | SUPERSEDED | not imported by V6 |
| `agent_control_virtualization.lookup` mock | REJECTED CANONICAL LOOKUP | historical tests only |
| `timing_closure/` V1 | FROZEN NEGATIVE BASELINE | `TIMING_NO_GO` unchanged |
| `common_action_gateway_v2/` | ACTIVE | canonical Gateway; new opaque client mode |
| `cryptographic_closure.pir_backend` | ACTIVE GENERIC BYTE WRAPPER | historical capsule adapter is lazy only |
| `src/path_oram.py` descendants | OPTIONAL_PRIVATE_STATE_EXTENSION | not selection/activation privacy |

No frozen result or raw trace was deleted. The canonical README points only to
V6. Stale stage entrypoints remain reproducibility tools and are not presented
as runnable pieces of one architecture.

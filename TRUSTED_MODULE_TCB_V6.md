# Trusted-module TCB audit V6

Using the recorded non-comment code-line method in
`scripts/audit_tcb_v6.py`:

| Trust domain | Code LoC | Dependencies |
|---|---:|---|
| TrustedActionModule, including reused bootstrap | 406 | Python stdlib, `cryptography` X25519/HKDF/AES-GCM |
| Trusted Gateway V2, including commands | 2,030 | Go stdlib, OS shared memory/socket primitives |

Per-file evidence is `results_v6/tcb_inventory_v6.csv`. The trusted action
module is substantially smaller than the V5 905-LoC Control-IR runtime because
the compiler/interpreter and framework semantics are absent. Gateway LoC is a
separate trusted external domain and must not be merged into the enclave count.

Offline adapters, corpus tooling, SimplePIR server, experiment scripts, and
classifiers are outside the runtime TCB. The pinned SimplePIR **client** and its
cryptographic implementation would be additional dependency code in a deployed
TEE; this audit reports project-owned LoC and does not misleadingly count that
third-party library as zero.

# Current security assumptions V5

1. Enterprise attestation policy and the measured TEE/CVM hardware/runtime are
   trusted under the vendor confidential-computing model.
2. Cloud OS, orchestration, storage, Agent execution server, and native
   framework processes are untrusted and may inspect ordinary process memory.
3. Only verified bounded capsules enter the TEE Control Kernel; classifier and
   compiler output is not trusted without deterministic verification.
4. Session keys are provisioned only after fresh attestation of an approved
   measurement; production sealed restore has a non-rollbackable freshness
   anchor.
5. Local membership is used only when the full catalog is inside the TEE.
   Outsourced membership requires an audited PSI/OPRF protocol not presently
   implemented.
6. Official SimplePIR assumptions apply to read-only registry lookup. Optional
   ORAM applies only to mutable private state, never Agent/Tool activation.
7. Public profile selection precedes private execution and does not depend on
   Agent, route, or private trajectory.
8. STRICT uses common private lookup/Gateway schedules and confines sensitive
   CLOUD_LOCAL Tools to TEE/common trusted boundaries.
9. CommonActionGateway effect guarantees depend on declared provider
   idempotency/reconciliation contracts.
10. Timing, resource, microarchitectural, physical, DoS, malicious firmware,
    global traffic, and confidential-GPU channels are outside the current
    validated evidence unless separately measured.

Assumptions 1 and 4 are target deployment assumptions only. They are not met by
the local functional backend.

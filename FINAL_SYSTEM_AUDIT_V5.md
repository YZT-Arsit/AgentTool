# Final system audit V5

## Status dashboard

| Required status | Result |
| --- | --- |
| FUNCTIONAL_E2E | **PARTIAL** — one Tool workflow passes STANDARD/LONG; SHORT fails; full strata not closed |
| WHOLE_WORKFLOW_EXECUTABLE_COVERAGE | **33/151 = 21.85%** fully executable; 97 partial; 21 unsupported |
| FRESH_SEMANTIC_FIDELITY | **12/12** on the frozen V3 bounded holdout |
| IR_CLASSIFIER_FALSE_ACCEPT_RATE | **0%** max on three grouped splits; **2.586%** worst cross-framework at 0.9 threshold |
| IR_VERIFIED_LOWERING | **1 functional capsule accepted in unit evidence; 0 corpus promotions** |
| STRICT_ROUTE_PRIVACY | **OPEN** — symbolic/unit public-view equality only |
| ENTERPRISE_ROUTE_LEAKAGE | `route_class` explicitly public in CONFIDENTIAL_ENTERPRISE and ENTERPRISE_EFFICIENT |
| STRUCTURAL_PRIVACY | **OPEN** for V5 long-horizon whole workflows |
| SIZE_PRIVACY | **OPEN** for V5 long-horizon whole workflows |
| TIMING_PRIVACY | **OPEN / NOT_TESTED** |
| RESOURCE_PRIVACY | **OPEN / NOT_MEASURED V5** |
| EFFECT_RECOVERY | READ_ONLY PASS; IDEMPOTENT PASS with contract; NON_IDEMPOTENT PARTIAL |
| RUNTIME_TCB | TEE Control Runtime 905 approximate code LoC; Gateway 1,604; optional reference runtime 374 |
| DUMMY_HEAVY_OPS | **0** in all V5 horizon development runs |

## TEE amendment outcome

V5 now correctly treats process separation as engineering isolation, not a
confidentiality boundary. Keys, decryption, membership/PIR client work, capsule
plaintext, logical identity, verification/interpreter state, policy/effect
authorization, and outbound encryption belong in an attested TEE/CVM. The
ordinary cloud plane remains untrusted.

The target dataflow is implemented behind a TEE interface with a local
trusted-process backend. Measurement allow-listing, challenge binding,
ephemeral session establishment, AEAD payloads, key rotation on restart,
integrity-protected sealing, capsule verification, local membership, profile
policy, and Tool-placement fail-closed behavior have unit coverage. Hardware
attestation and rollback protection are not tested; the local process is not a
security substitute.

## Functional repair

The old Pacer discarded late results after their request session. V5 retains
them for the next pre-existing public slot. STANDARD and LONG now deliver 3/3
results and return; SHORT delivers 2/3 and fails. The repair does not alter slot
count, size, cadence, or lifetime. Full V5 E2E remains partial because route,
Agent-as-Tool, and all long-horizon families have not passed one unified
hardware-backed path.

## Generality and frontend

IR-v1 remains 3,574/7,386 = 48.39%. V3 semantic holdout passes 12/12, but
whole-workflow coverage remains 33/151. All 1,904 MIXED/UNPROVEN instances stay
unsupported. The offline classifier is useful for triage but its cross-framework
false accepts prohibit direct authorization. Deterministic verification and
semantic comparison remain mandatory.

## Profiles and routing

STRICT symbolically equalizes internal/external public route projections using
a real-or-dummy private lookup plus the common Gateway slot. The two weaker
profiles intentionally reveal route class; ENTERPRISE_EFFICIENT may also reveal
a configured internal Tool category. The local routing audit is not a live PIR
or TEE privacy result. No audited offline PSI dependency exists, so
`CRYPTOGRAPHIC_PSI = NOT_IMPLEMENTED`; local membership is used when the catalog
is inside the TEE.

## Security exclusions and blockers

Excluded are microarchitectural/cache channels, physical attacks, malicious
CPU/firmware beyond attestation, DoS, TEE implementation bugs, global traffic
analysis, and confidential-GPU leakage. TEE placement does not close transport
metadata, timing, or resource traces.

The three strongest blockers are:

1. no hardware TEE attestation, sealed rollback anchor, or live confidential
   deployment evidence;
2. V5 long-horizon functional coverage is incomplete, so structural/size
   privacy was correctly not rerun;
3. whole-workflow executability is only 33/151, with 1,430 extractor-ambiguous
   MIXED instances.

## Conclusion

V5 is a **CONTROLLED PROTOTYPE WITH A SOUND TARGET TRUST BOUNDARY**, not a
validated confidential system. The architecture amendment fixes an invalid
process-isolation assumption and materially reduces the intended TCB relative
to full-framework enclave baselines. The next step is a hardware-backed
attestation/rollback integration plus unified functional E2E closure; only then
freeze and run a new long-horizon structural/size holdout. Timing remains a
separate reference-platform experiment.

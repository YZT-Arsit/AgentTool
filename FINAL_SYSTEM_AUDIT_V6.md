# Final V6 system audit

V6 successfully removes Control IR from the canonical privacy path and closes
the encrypted descriptor/PIR component. It does **not** yet validate the full
live action trajectory.

## Independent status

- `CANONICAL_IR_DEPENDENCY`: **NONE**
- `LOCAL_TRUSTED_MODULE`: **PASS** for local functionality; no malicious-host claim
- `HARDWARE_TEE_ATTESTATION`: **NOT_TESTED**
- `PIR_CLIENT_BOUNDARY`: **PASS** locally, hardware placement untested
- `REAL_SIMPLEPIR_DESCRIPTOR_PATH`: **PASS**
- `PIR_100K`: **PASS**
- `UNIFIED_PRIVATE_REGISTRY`: **PASS** as a selection component
- `HIERARCHICAL_RESOLUTION`: **PASS** functionally with declared route leakage
- `ACTION_MEDIATION_COVERAGE`: **894/1,370 = 65.26% fully mediated**; 473 partial; 3 unsupported
- `FRESH_ACTION_SEMANTIC_FIDELITY`: **16/16** on the frozen one-shot action holdout
- `GATEWAY_FUNCTIONAL`: **PARTIAL**
- `STRICT_STRUCTURAL_PRIVACY`: **OPEN**
- `STRICT_SIZE_PRIVACY`: **OPEN**
- `ENTERPRISE_ROUTE_LEAKAGE`: **internal/external route and configured cloud-local Tool class are declared**
- `LONG_HORIZON_PRIVACY`: **OPEN**
- `TIMING_PRIVACY`: **OPEN / NOT_TESTED**
- `PACKET_LEVEL_TIMING`: **OPEN**
- `RESOURCE_PRIVACY`: **OPEN**
- `EFFECT_RECOVERY`: read-only PASS; idempotent PASS with provider contract; non-idempotent PARTIAL/fail-closed; Gateway restart OPEN
- `TRUSTED_MODULE_TCB`: **406 code LoC**, Python stdlib + cryptography + pinned SimplePIR client dependency
- `GATEWAY_TCB`: **2,030 code LoC**, Go stdlib/OS primitives
- `DUMMY_HEAVY_OPS`: **0**

## Strongest positive evidence

The 100K database is real, encrypted, fully preprocessed, and correctly queried
through official SimplePIR. The recovered descriptor feeds the IR-free trusted
module and fixed Gateway wire format without secret plaintext. The action
semantic holdout passes across two pinned framework corpora.

## Strongest falsification finding

The only completed live opaque-Gateway arm delivered 43/50 results despite 50
effects executing, so functional semantics were not preserved within the chosen
public profile. The paired arm then hit a host Application Control block. A
constant format is therefore not cited as privacy evidence. The live STRICT and
long-horizon claims remain open.

V6 is a coherent component prototype, not a validated end-to-end confidential
agent system. The next experiment is a fresh, pre-frozen, functionally passing
paired Gateway run on the intended offline Linux host with an actual hardware
TEE backend evaluated separately when available.

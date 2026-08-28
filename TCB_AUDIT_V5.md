# TCB audit V5

## Measured source inventory

| Component | Files | Approx. code LoC | In TEE? |
| --- | ---: | ---: | --- |
| V5 TEE Control Runtime | 10 | 905 | target yes |
| IR-v2 reference semantic runtime | 2 | 374 | optional/reference; not all required in minimal deployment |
| CommonActionGateway | 15 | 1,604 | separate trusted CVM/boundary or co-located TEE service |
| compiler/classifier/harness group | 5 | 567 | no |
| full OpenAI framework baseline | 307 | 108,200 | baseline only |
| full Microsoft core baseline | 81 | 48,652 | baseline only |

The target `VERIFIED_SMALL_CONTROL_KERNEL` is therefore 905 approximate project
code LoC before the optional 374-LoC reference runtime, versus tens of thousands
to 108k LoC for a `FULL_TRUSTED_RUNTIME`. Exact per-file rows are in
`TCB_INVENTORY_V5.csv`.

Runtime dependencies are Python standard library, `cryptography` and its native
backend, the pinned official SimplePIR dependency, OS/TEE ABI, and (when
separate) the Go Gateway standard-library stack. The local backend uses X25519,
HKDF-SHA256, and AES-GCM from `cryptography`; it invents no primitive.

Private runtime state includes 64 bytes of session key material, 1,024 bytes per
installed capsule, bounded Control Kernel/call-stack/result state, membership/
PIR client state, and sealed journal/checkpoint state. Public interfaces are
attest, provision, submit ciphertext, fixed slot, and sealed checkpoint.

`HARDWARE_TEE_ATTESTATION = NOT_TESTED`. The local process backend does not
reduce trust in the host and cannot prevent rollback without an external
freshness anchor.

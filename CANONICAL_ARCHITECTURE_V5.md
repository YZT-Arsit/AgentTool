# Canonical Architecture V5

Status: **development architecture; hardware confidential execution is not yet
validated**. This document supersedes V3/V4 as the active design target without
altering their frozen evidence.

## Architecture

```text
native OpenAI/Microsoft source (untrusted build input)
        |
offline extractor + optional classifier (not runtime TCB)
        |
CandidateTypedIR + source map
        |
deterministic verifier (runtime TCB)
        |
approved fixed-width verified capsule
        v
enterprise verifier ---- remote attestation ---- attested TEE/CVM
                                              small Control Kernel
encrypted prompt/data ----------------------> private capability extraction
                                              local/PSI membership client
                                              PIR client + recovery
                                              capsule/control/result plaintext
                                              policy/effect authorization
                                              outbound envelope encryption
                                                        |
                                                        | fixed opaque ABI
                                                        v
untrusted OS/orchestrator/storage/Agent compute plane -> CommonActionGateway
                                                        -> one real heavy primitive
```

The TEE/CVM—not process separation—is the confidential execution anchor. The
native frameworks are compiler inputs and evaluation dependencies; they are not
placed inside the enclave. The currently executable backend is a local trusted
process that exercises interfaces and key flow only. It gives no protection
against cloud root, memory inspection, or rollback.

```text
HARDWARE_TEE_ATTESTATION = NOT_TESTED
CRYPTOGRAPHIC_PSI = NOT_IMPLEMENTED
TIMING_PRIVACY = OPEN / NOT_TESTED
```

## Runtime TCB

The intended runtime TCB contains only:

- attestation/bootstrap and key lifecycle;
- deterministic capsule verifier;
- bounded Control IR decoder/interpreter and private call stack;
- private membership/PIR client endpoints;
- private policy, effect, result, and sealed-checkpoint state;
- fixed-envelope encoder/decoder and Gateway enforcement.

The compiler/classifier, corpus tools, native frameworks, provider emulator,
and experimental analysis are outside the runtime TCB. Classification can
propose a lowering but cannot authorize it; the verifier and semantic gate can
only accept a bounded source-mapped capsule.

## Resolution and execution

`A_enterprise` is a relatively small catalog of approved internal Agent
capabilities. `A_external` is a potentially large set of signed/source-traceable
descriptions that must compile to the same verified bounded IR. The confidential
runtime derives a private capability token, performs local membership when the
catalog is resident, or invokes a private-membership client when it is not.

An internal hit performs a real PIR lookup of the fixed Agent capsule. An
external miss invokes the external discovery adapter. Under `STRICT`, both
consume the same public lookup/Gateway schedule; the miss consumes a reserved
dummy PIR row. Under weaker profiles, the route bit is declared public.

Logical `HANDOFF` and `CALL_AGENT` mutate confidential state and the private
call stack. They never start an Agent-specific process, URL, worker, or queue.
Heavy model/Tool operations run once behind common boundaries. Cover slots do
not execute LLMs, Tools, or Agents.

## Primitive roles

| Primitive | Exact role | Does not establish |
| --- | --- | --- |
| TEE/CVM | plaintext/control/key execution anchor | transport-metadata or side-channel privacy |
| PIR | read-only private Agent-record lookup | Agent activation, Tool endpoint, mutable access privacy |
| optional state ORAM | mutable outsourced private-state access | Agent/Tool invocation privacy |
| Control Virtualization | logical Agent identity as private state | payload confidentiality without TEE/encryption |
| fixed transcript | count/order/size profile | live timing without observer-boundary pacing |
| Common Gateway | common downstream boundary/effect gate | global destination privacy beyond its observer |

## Frozen evidence boundary

- IR-v1 remains 3,574/7,386 = 48.39%.
- IR-v2 72/72 remains development regression evidence.
- The V2 semantic holdout remains 8 valid passes and 12 `HARNESS_INVALID`.
- Whole-workflow source-file coverage remains 33 full, 97 partial, 21 unsupported.
- The old long-horizon experiment remains functionally failed despite equal
  shapes and AUC 0.500.
- Gateway V1 remains `TIMING_NO_GO`; V5 timing is open.

No V5 interface or document changes those results.

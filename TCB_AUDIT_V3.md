# TCB audit V3

## Boundary

The trusted computing base is not the full OpenAI or Microsoft Agent runtime.
Framework objects are compiler inputs. The runtime TCB is the fixed capsule
decoder/interpreter, Privacy Kernel, PIR client integration, CommonActionGateway
Worker/Pacer, cryptographic framing, provider routing, and effect gate.

The untrusted Agent Cloud contains only `cloud_slot_proxy/` and observes public
profile/session/slot metadata plus opaque fixed frames. Local process separation
on the experimental host is an implementation aid, not protection from host
root. The formal deployment requires the Privacy Kernel and Gateway to execute
in trusted domains distinct from the untrusted Cloud observer.

## Source size

Counts below are physical lines and an approximate nonblank/non-comment source
count. They are reproducible inventory measures, not complexity or assurance
scores.

| Group | Files | Physical LoC | Approx. code LoC | Trust role |
| --- | ---: | ---: | ---: | --- |
| IR-v2 ABI/interpreter + Privacy Kernel protocol/control | 4 | 812 | 696 | trusted runtime |
| Gateway Worker/Pacer/protocol/rings/providers/platform adapters and trusted command entrypoints | 17 | 1,745 | 1,605 | trusted runtime; excludes legacy untrusted cloud client code |
| PIR scheduler, subprocess adapter, and combined local SimplePIR bridge | 3 | 679 | 612 | mixed integration; client side trusted, server side logically untrusted |
| **Project runtime/integration total** | **24** | **3,236** | **2,913** | experimental TCB/integration surface, including local provider emulator and combined bridge |
| Versioned compiler and current canonical/real-model orchestration tooling | 9 | 1,199 | 1,046 | trusted build/test tooling, not online interpreter TCB |
| Pinned upstream SimplePIR `pir/` non-test Go sources | 10 | 1,938 | 1,505 | trusted client cryptography plus server primitive dependency |

The counts were refreshed after the IR-v2 private-state and partial
Agent-as-Tool additions. The Gateway dominates project runtime LoC. Therefore
the accurate current claim is “a bounded control interpreter plus a larger
trusted mediation Gateway,” not “only a few hundred trusted lines.”

## Trusted dependencies

- Python standard library.
- `cryptography` AES-GCM implementation and its native crypto backend.
- Go standard library, including networking, HTTP, JSON, mmap/syscall, and AES-GCM.
- Pinned `ahenzinger/simplepir` commit
  `e9020b03bf2872c75b8954e749e32408b5db87ed`.
- Operating-system process, file-permission, monotonic-clock, shared-memory, and
  socket semantics.

OpenAI Agents SDK and Microsoft Agent Framework are compiler/evaluation
dependencies. They are not required by the online capsule interpreter after a
capsule is produced. The current E2E harness still instantiates an OpenAI Agent
at compilation time on the same machine; that is tooling, not the intended
deployment boundary.

## Trusted state

### Persistent or checkpointed

- PIR client hint/state: 8,798,208 bytes at the N=1,000 E2E scale and
  75,309,056 bytes at the measured N=100,000 scale.
- Cached capsules: 1,024 bytes per cached logical Agent plus map overhead.
- Private Agent/session state and model context: currently in memory; a durable,
  bounded representation is not yet implemented.
- Effect idempotency records: currently in-memory only in the Gateway Worker and
  provider emulator. They do not survive a Worker restart.

### Ephemeral

- One 16-byte AES-GCM experiment key, written to a mode-0600 temporary key file,
  passed by path only, and deleted after the run.
- Logical Agent ID, capsule plaintext, current state/event, pending action,
  pending result, private Tool call, Tool results, private-value map, model
  context, and failure class.
- PIR query randomness and recovered capsule plaintext.
- Gateway shared request/result rings and provider endpoint configuration.

Keys were not logged or passed as normal command-line values in the canonical
run.

## Private APIs

- `PrivateAgentLookup(index) -> AgentCapsule` inside the Privacy Kernel.
- `ControlKernel.tick()` and `ControlKernel.accept_result()`.
- fixed `PrivateOperation` and `ResultRecord` ABIs between trusted kernel and
  Gateway.
- Worker-to-Pacer fixed shared-memory result ring.
- trusted provider configuration and provider adapter execution.

The public Cloud proxy API contains only address, public profile, fixed frames,
and public trace path.

## Unsupported or incomplete runtime features

- corpus-wide state/session semantics;
- arbitrary Python callbacks, middleware, and guardrails;
- general multi-Tool lowering into the canonical fixed capsule ABI;
- Agent-as-Tool beyond the partial bounded private call-stack implementation
  (native framework call/return projection remains untested);
- durable HITL continuation;
- bounded fork/join;
- runtime PIR capsule retrieval on a handoff cache miss;
- durable effect idempotency and ambiguous post-effect reconciliation;
- bounded/durable model context;
- malicious-host isolation proof, timing privacy, resource privacy, and
  packet-level traffic privacy.

## Important integration limitation

The current SimplePIR bridge executes client and server algorithm roles in one
local Go process while preserving separate client/server trace artifacts. This
does execute the real cryptographic construction and full preprocessing, but it
is not a deployed network/process-separated PIR service. A production boundary
must split those roles without introducing index-bearing application logs.

## Audit conclusion

The project does not move the full Agent framework into the trusted runtime, and
the validated interpreter core is small. Nevertheless, the trusted Gateway and
cryptographic integration are material. TCB status is **measured but not yet
minimized or hardened**; durable state/effect recovery and a physically separated
PIR deployment are open engineering/security requirements.

# Agent Control IR specification

## Fixed ABI

Each capsule is 1,024 bytes: a 64-byte header followed by at most thirty
32-byte transition rows and zero padding. The header contains the logical ID,
row count, runtime profile, instruction handle, and source digest. These are
private capsule fields and never enter the executor's host-visible trace.

Each transition row contains fixed-width opcode, event, state, next-state,
target handle, auxiliary/flags, and a hashed audit label.

## Opcodes

| Opcode | Semantics |
| --- | --- |
| `LLM` | Invoke the common model primitive. |
| `TOOL` | Invoke a protected Tool handle through `ToolExecutionAdapter`. |
| `HANDOFF` | Replace the private logical Agent ID; retain the same executor. |
| `STATE_GET` / `STATE_SET` | Reserved declarative state operations. |
| `POLICY` | Reserved declarative policy operation. |
| `RETURN` | Terminate and return a protected result. |
| `NOOP` | Consume a fixed slot without heavy work. |
| `BRANCH` | Reserved for declarative bounded branches; arbitrary Python predicates are unsupported. |

`LLM`, real Tool work, and large processing are shared primitives, not embedded
in the capsule. The evaluator performs a fixed full-row scan and selects the row
matching `(state,event)`. It is a semantics simulator, not secure computation.
At the maximum row count, the recorded engineering estimate is 4,744 Boolean
gates over 1,027 secret bytes and 12 public profile bytes; no cryptographic
circuit-security or communication claim is made.

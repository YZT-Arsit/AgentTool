# Current Security Definition

## Public leakage

For observer `O`, `L_O(tau)` includes the public protocol/profile version,
database dimensions, public PIR/control/I/O schedules, public session policy,
fixed size bucket, public outcome class, and agreed public effect projection.
Executions are compared only when these values match.

`View_O^Gamma(tau)` is observer-specific:

- `O_registry`: SimplePIR server query/answer transcript and public database
  dimensions;
- `O_agentcloud`: U process identity, public header, opaque fixed ciphertext,
  slot count/order/width, common Gateway endpoint, tunnel lifetime, and declared
  socket/resource/timing features;
- `O_gateway`: trusted and not an adversary in the base model;
- `O_provider`: its own plaintext request/result; it is not promised privacy
  about the operation it executes.

For legal trajectories with `L_O(tau_0)=L_O(tau_1)`, the intended property is:

```text
View_O^Gamma(tau_0) ~=c View_O^Gamma(tau_1)
```

## Composition argument and current evidence

1. **PIR selection lemma.** Official SimplePIR hides the selected row from
   `O_registry` under its construction assumptions. Status: primitive integrated
   and locally exercised; PASS.
2. **Control-placement lemma.** U receives no logical Agent ID, index, capsule,
   opcode, provider, payload, result, or key. Status: schema/source/unit PASS and
   live-trace PASS for the validated Linux single-Tool path.
3. **Control-transcript lemma.** Fixed common executor/slot identity, count,
   order, and width are independent of private progress. Status: live functional
   exact structural/size equality PASS for seven completed workflows under one
   identical public profile; a 42-episode structural/size-only classifier sanity
   check is at chance. Long-horizon and corpus-scale privacy remain OPEN.
4. **Handoff lemma.** `HANDOFF(j)` changes trusted logical state only. Status:
   exact dynamic semantic PASS on the evaluated handoff subset.
5. **Gateway-destination lemma.** U observes only CommonActionGateway. Status:
   implementation/unit/live validated-subset PASS.
6. **Payload lemma.** REAL/NOOP and RESULT/WAIT use fixed-width AES-GCM envelopes
   with authenticated public headers. Status: Go/Python unit PASS.
7. **Timing lemma.** Fixed-rate release is independent of private work only if
   isolated Pacer timing is verified at the observer boundary. Status: NOT
   TESTED for V3; V1 is a historical FAIL.
8. **Effect lemma.** Cover slots cannot create effects and operation IDs gate
   effectful requests. Status: unit PASS, normal-completion PASS, private
   timeout/error/interruption tests PASS, and duplicate-ID once-only PASS;
   timeout-after-effect reconciliation and restart durability remain OPEN.

The conjunction is **not currently established**. The former Tool-loop and
Linux live-Gateway blockers are repaired for the validated single-Tool stratum,
but corpus-wide executable support, runtime PIR fetch on handoff, long-horizon
repeated/frequency privacy, durable effect reconciliation, timing, and resource
privacy remain open. The current definition is therefore a target with explicit
component evidence, not a complete system theorem.

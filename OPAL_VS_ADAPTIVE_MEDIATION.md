# Opal vs Adaptive Mediation

Primary source: [Opal: Private Memory for Personal AI](https://arxiv.org/abs/2604.02522).

## Direct answers

1. **What is one Opal request?** A memory ingestion or query/retrieval request to trusted-hardware inference enclaves backed by untrusted ORAM storage.
2. **What determines its public trace shape?** Public parameters fix inter-enclave calls and ORAM batch sizes; query-dependent filtering and graph traversal remain inside the enclave.
3. **Does Opal model private authorization causing additional agent actions?** Not in the Stage-9 sense established from the paper. Its core model concerns personal-memory storage, retrieval, maintenance, freshness, and fixed request traces.
4. **Does it model external effects?** The evaluated interface is memory access, not a no-dummy-effect tool commit such as sending a message.
5. **Does it model local consent/persistence/retry?** No such approval trajectory is identified in the cited design.
6. **What differs in Stage 9?** The private state is security mediation state that changes later approval, consent, provenance, verification, and effect-control actions. The equivalence class fixes the real external effect, and normalization may pad only internal mediation.

## Collision

The collision is substantial. Opal already demonstrates the central systems pattern: move data-dependent reasoning into trusted execution and expose a fixed observable request schedule to untrusted storage. Stage 9 cannot claim fixed request shapes, ORAM-backed padding, or whole-request trace normalization as new.

The narrower difference is the security/effect semantics:

- private standing authorization or provenance state can create additional interactive mediation rounds;
- public effect occurrence belongs to the leakage definition;
- dummy external effects are forbidden;
- authorization denial must dominate normalization;
- overflow must fail closed for the entire public class;
- a mediation IR marks private guards and external commit operations.

These are meaningful domain constraints, but Stage 9 does not show that they require a fundamentally different cryptographic primitive.

## Verdict

```text
OPAL COLLISION: PARTIALLY DEFEATED
```

Stage 9 separates adaptive security/effect trajectories from Opal's memory request, but its normalization principle is closely aligned with Opal's fixed-observable-trace design.

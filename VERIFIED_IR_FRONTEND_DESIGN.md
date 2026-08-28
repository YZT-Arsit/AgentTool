# Verified IR frontend design

```text
source + pinned provenance
 -> deterministic extractor
 -> optional offline classifier proposal
 -> CandidateTypedIR
 -> deterministic boundedness/type/effect verifier
 -> semantic differential test
 -> signed capsule manifest
 -> TEE runtime verifier
 -> install or reject
```

The classifier/compiler are outside the runtime TCB. Each candidate node must
retain a source span. The build verifier checks types, allowed opcodes, public
bounds, state scopes, Tool/Agent handles, side-effect class, and control-flow
determinism. The TEE verifier independently checks capsule digest, compiler
version, source-manifest binding, runtime profile, state/transition bounds,
valid branch targets, and bounded return before plaintext installation.

Arbitrary Python callbacks, unbounded dynamic control, native plugins, and
undeclared effects remain unsupported. A hallucinated classifier proposal is a
normal reject path and cannot enlarge the TCB or authorize execution.

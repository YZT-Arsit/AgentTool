# Mediation IR

## Purpose

The Stage-9 IR is a small security-control-flow representation, not an agent programming language. It exists to make private guards explicit and give one task-independent normalizer enough structure to calculate a fixed public horizon and commit slot.

## Operations

The implemented operations are:

```text
RESOLVE
AUTHORIZE
CHECK_PROVENANCE
REQUEST_LOCAL_CONSENT
PERSIST_AUTHORIZATION
REBUILD_PROVENANCE
PERSIST_PROVENANCE
VERIFY_AUTHORIZATION
PREPARE_EFFECT
COMMIT_EFFECT
RETURN_SANITIZED
```

`COMMIT_EFFECT` is the only operation marked `external_effect=True`. The constructor rejects any other external-effect annotation. `RETURN_SANITIZED` and the effect occurrence are public; authorization, provenance, consent, verification, and binding operations are private.

## Guards

Every guard has an explicit visibility annotation. The natural scenarios use private guards over actual mediator state:

- `permission_exists` / `permission_missing`;
- `provenance_exists` / `provenance_missing`;
- `verification_cached` / `extra_verification_required`.

The unconditional transition guard is public. No transition consults `private_label`, `hidden_class`, or another experiment-only bit. Labels are derived after trace capture.

## Programs

The three programs are acyclic state machines:

```text
Authorization:
  CHECK -> READY -> COMMIT
       \-> CONSENT/PERSIST -> VERIFY -> READY -> COMMIT

Provenance:
  CHECK -> READY -> COMMIT
       \-> REBUILD/PERSIST -> READY -> COMMIT

Extra verification:
  CHECK -> READY -> COMMIT
       \-> VERIFY -> READY -> COMMIT
```

Every path produces the same allowed final effect in the positive pairs. A separate denial test verifies that failed consent produces no effect.

## Compiler input and output

`AdaptiveNormalizer.compile(program, horizon)` inspects graph paths and \(H\). It does not inspect the public task name or private guard values. It returns:

- maximum required path length;
- overflow status;
- the fixed public round slots;
- the final public commit round, when admitted.

At execution, semantic pre-commit transitions occupy the earliest slots, unused slots perform indistinguishable private ORAM accesses, and the single real effect occurs in the final public slot. `SEND_MESSAGE` and `SHARE_DOCUMENT` use the same compiler. The effect endpoint comes from a public task schema after compilation.

## Generality boundary

The compiler demonstrates one reusable rule over three small acyclic machines. It does not synthesize optimal schedules, handle unbounded loops, hide all timing, or prove that arbitrary mediator code can be lowered automatically. Calling it a full compiler would overstate the artifact; “bounded normalizer over annotated mediation IR” is the accurate description.

Implementation: [`stage9_adaptive/ir.py`](stage9_adaptive/ir.py) and [`stage9_adaptive/runtime.py`](stage9_adaptive/runtime.py).

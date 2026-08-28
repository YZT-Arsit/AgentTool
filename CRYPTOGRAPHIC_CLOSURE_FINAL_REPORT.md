FINAL DECISION: CONDITIONAL_GO

REAL PIR: PASS  
MULTI-ROUND PRIVACY: OPEN  
TOOL PRIVACY: OPEN  
TIMING PRIVACY: OPEN  
RESOURCE PRIVACY: OPEN

# Cryptographic Closure and Multi-round Falsification

## Executive finding

The conditional Agent Control Virtualization result survives real cryptographic lookup and repeated observation for
the **structural/serialized-size observer**, including across fresh sessions. It does not survive timing or coarse
resource observation. The correct decision is therefore `CONDITIONAL_GO`, not `GO`.

The three strongest reasons to continue are:

1. Official SimplePIR is in the actual B2 path, full preprocessing completes at 100K, and sampled capsules recover
   exactly.
2. Fresh raw queries, common executor frames, repeated handoffs, and cross-session traces expose no stable target
   identifier; tested identity/linkability attacks remain at their controls.
3. The candidate performs no dummy heavy computation and all action slots use one fixed protocol boundary.

The three strongest limitations are:

1. Tool timing makes class, frequency, rare occurrence, transition, and repeated-target structure highly
   distinguishable.
2. Coarse CPU/memory behavior classifies action type above chance; fixed packets do not solve resource leakage.
3. Remote destination privacy depends on a trusted/common egress boundary; an observer after egress is outside the
   validated claim.

## Candidate path actually evaluated

```text
official SimplePIR query
    -> exact 1,024-byte Agent capsule
    -> common AgentControlExecutor
    -> fixed four-slot, 1,024-byte control transcript
    -> one common Tool/action boundary
    -> only the required real heavy primitive
```

No Path ORAM or ORAM-like mechanism is used for Agent selection, Agent dispatch, Tool identity, or invocation. Any
retained Path ORAM is an `OPTIONAL_PRIVATE_STATE_BACKEND` only.

## Real PIR closure

The official `ahenzinger/simplepir` repository at commit
`e9020b03bf2872c75b8954e749e32408b5db87ed` was integrated locally. Upstream correctness tests passed. The final
100K run used exactly 100,000 logical 1,024-byte rows plus 1,024 bytes of physical padding. Full preprocessing took
23.507 s; mean online query generation, answer, and recovery were 6.643, 14.046, and 2.950 ms. Upload/download were
36,388/37,180 bytes. All 10 indices recovered exactly.

At 100K, persistent client state was 75.3 MB and peak allocated memory 1.44 GB. This is runnable on the available
machine, but it is not a low-client-state or production-optimized result.

The actual pipeline uses the recovered bytes as an `AgentCapsule`; the prior mock lookup appears only in historical
baseline artifacts and is not involved in final inference.

## Repeated observation

The final interleaved run executed 16,000 real PIR queries over M0-M7. Same-target raw-query AUC was 0.490/0.494.
Ten-way Agent classification macro-F1 was 0.093/0.088 at chance 0.1. No frequency, rare-Agent, or transition attack
on raw query bytes reached permutation significance in this sample.

Cross-session linking across 12 independent bridge processes produced AUC 0.476 and 0.458. Repeated queries used
fresh query randomness and no stable target pseudonym was found.

Timing is the counterexample: the frequency attack reached AUC 0.738 with permutation p=0.0476. Multi-round privacy
is therefore open in the full observer, even though cryptographic/structural identity privacy closes.

## Handoff

H0-H3 use the same physical `AgentControlExecutor` and protected control-slot ABI. Logical destinations remain in
private ground truth; no `/agent/B`, B-specific worker, process, or queue appears in the host trace. This revalidates
the earlier real-framework HANDOFF semantics under repeated structural observation.

## Action type

Every AGENT/LLM/TOOL/NOOP slot actually crosses the same common RPC once with a 1,024-byte request and response.
Structural and size classifiers are exactly at 0.25 chance. Timing reaches 0.544 and resource-only classification
0.473; all features reach 0.577. Action-type privacy is not closed against those observers.

## Tool boundary

Real temporary-file, controlled HTTP, and cloud-local compute operations execute behind `CommonToolExecutor`.
Direct baselines expose three distinct destinations. The protected structural/size view uses the same endpoint and
fresh equal-width ciphertext.

Tool timing is a decisive failure: three-way class top-1 reaches 0.770, repeated-target AUC 0.831, and frequency,
rare, and transition attacks approach 1.0. Structural/size Tool privacy passes, but complete Tool privacy is open.

The remote result is conditional on a common trusted egress being the observer boundary. The prototype does not hide
the destination from an observer after that egress.

## Heavy-compute invariant

Cover/NOOP frames terminate inside the common boundary. They do not invoke an LLM or concrete Tool. For a one-heavy
operation candidate episode:

- real Agent/LLM/Tool operations: exactly those required by the workflow;
- dummy heavy operations: 0;
- PIR operations: one per private capsule selection;
- fixed frames: four per selected public profile.

The method does not degenerate into k-cover or N-cover real execution.

## Falsification findings and assumptions

- PIR target privacy relies on the SimplePIR security construction; classifiers are only sanity checks.
- The Windows 100K bridge required an upstream uncompressed matrix-answer path because the packed kernel crashes for
  a non-multiple-of-eight row count. Performance numbers include this adapter.
- The 100K database scales 22 real-framework prototypes into generated rows; this is scale evidence, not 100K real
  framework diversity.
- Timing, resource, post-egress traffic observation, GPU telemetry, and microarchitectural channels remain open or
  outside the claimed pass.
- The common Tool boundary is a trusted privacy boundary. Moving it onto the honest-but-curious compute plane without
  confidential execution would reveal decrypted Tool class.

## Decision rationale

`GO` is rejected because timing/resource Tool and action traces remain distinguishable. `NO_GO` is also rejected:
real PIR is operational at 100K, the full structural/size candidate path has no stable target identifier, logical
handoff stays virtual, the claimed Tool classes use a common endpoint, and dummy heavy work remains zero.

The defensible result is:

> Real cryptographic private selection plus common-executor virtualization closes the evaluated long-horizon
> Agent-identity channel for structural and serialized-size observations, but high-assurance privacy remains
> conditional on timing/resource shaping and an explicitly trusted common Tool egress.

See `FINAL_SECURITY_MATRIX.md` for all 20 required statuses and the companion reports for raw evidence.

## Verification

- Repository regression suite: **118 passed** in 26.39 s.
- Official upstream SimplePIR tests: **PASS** (`results_crypto_closure/official_simplepir_tests.txt`).
- Explicit host/private trace separation tests: **PASS**.
- 100K recovered-record and fresh-query invariants: **PASS**.

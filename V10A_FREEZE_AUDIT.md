# V10A canonical confirmatory holdout freeze audit

## Outcome

V10A completed as a **freeze-only** phase. Thirty-two fresh semantic cases and ten structural/size pairs are frozen. No selected case was executed, no selected-case Relay trace exists, and no privacy/semantic result file was produced.

## System and Linux rebuild

- Accepted repository commit: `70709d3ea6aa15f2b5a9fddee0559d28509c0653`.
- System freeze SHA-256: `2f2fb558bbea484c8637409e1355221c989cbebae3f40cbabe3c7d45c6ed92b3`.
- Canonical source was copied into an isolated offline GOPATH together with the locally authorized `third_party/ohttp-go` tree and vendored dependencies.
- Linux binary was rebuilt from source; SHA-256: `183d4521cc3326ae261e1b221d544afdb33f8db7d1f986ea026a79372894e598`.
- Go workspace tests: PASS.
- RFC 9458 tests: PASS with `go test -vet=off`. Go 1.26 vet rejects one upstream test's non-constant `Fatalf`; no production/dependency source was changed.
- RFC 9292 adapter tests: PASS.
- Relevant Linux Python tests: 27 passed.
- Real SimplePIR descriptor smoke: PASS for two independently selected descriptor rows.
- V10 harness and V9.1 profile/projection fixture tests: 20 passed.
- Full Windows repository regression: 223 passed. An initial run had four setup-only ACL errors in a stale user pytest temp directory; the identical suite passed using a fresh workspace-local `--basetemp`.

The smoke and regression inputs are prior/synthetic development fixtures, not V10 cases.

## Public profile

`V10-STRICT-H50-C1` was written before selection. Its security-relevant values are mechanically equal to V9.1 H50: capacity/admission 50, total rounds 111, one session, 5 ms public period, 50 ms completion bound, one terminal round, BHTTP 1024/768, final OHTTP 1079/800, suite `(key=7, KEM=32, KDF=1, AEAD=1, epoch=3)`, one persistent local Relay/Gateway connection, and 555 ms scheduled lifetime. Only the public confirmatory identifier/phase metadata differ.

## Operation-ID ABI

All 438 frozen semantic and structural operation IDs are compact, globally unique across the generated freeze, and at most 32 UTF-8 bytes. A Linux helper serialized every ID through the accepted `RFC9292Codec` at the actual 1024-byte canonical request width and decoded it again. Result: PASS with no truncation.

## Semantic selection

- Eligible pool: 461 unique fresh sites after prior-case exclusion.
- Frozen cases: 32 (OpenAI Agents SDK 16; Microsoft Agent Framework 16).
- Selection: one seed, deterministic SHA-256 ranking, no outcome inspection.
- Families selected: OpenAI 12 Tool, 2 Agent-as-Tool, 2 handoff; Microsoft 16 Tool.
- Microsoft Agent-as-Tool shortage: zero fresh eligible sites remained after prior-case exclusion. This was recorded rather than replaced after execution.
- Preferred concentration cap was two sites per file. The Microsoft quota mathematically required a documented relaxation to three after the two-site pool was exhausted.
- Local deterministic scenarios cover read-only, idempotent/non-idempotent effects, errors, bounded local timeout, and multi-action behavior. These are frozen inputs/configurations, not frozen expected answers.

The frozen V6 corpus calls the fully mediated disposition `MEDIATED`; V10 preserves that source label and records its interpretation instead of relabeling the original corpus.

## Structural selection

Ten deterministic pairs are frozen under the single public profile: Agent identity, target/destination, action kind, private action count, repetition, frequency skew, rare target, transition pattern, private argument length, and completion behavior. The internal/external stratum remains `NOT_APPLICABLE` because no independently validated comparable internal-Agent path exists.

## Harness and immutability

The generic harness validates manifests and operation IDs, computes the accepted semantic/structural/size projections, enforces functional invalidation, and freezes prefix rules. Selected-case execution is guarded by an independently supplied `V10B` authorization file, which is absent. Harness-freeze manifest SHA-256: `24fde4109f2abab65e0b113a3e794dee0c3f6d4ae52c4a01e63e92fa5ae586e7`; authoritative source and frozen-input hashes are in that manifest.

Any change to runner, profile adapter, accepted projection, harness, profile, or manifest invalidates this freeze and requires a new version before execution.

## Required status

```text
PRE_HOLDOUT_SYSTEM_FREEZE: PASS
CANONICAL_SOURCE_REBUILD_LINUX: PASS
CANONICAL_BINARY_PROVENANCE: PASS
PRE_HOLDOUT_REGRESSION: PASS
V10_PUBLIC_PROFILE_FROZEN: PASS
V10_PROFILE_SECURITY_DIFF_FROM_V9_1: NONE
SEMANTIC_SELECTION_DETERMINISTIC: PASS
SEMANTIC_PRIOR_CASE_EXCLUSION: PASS
SEMANTIC_CASES_FROZEN: 32
STRUCTURAL_SELECTION_DETERMINISTIC: PASS
STRUCTURAL_PAIRS_FROZEN: 10
INTERNAL_EXTERNAL_STRATUM: NOT_APPLICABLE
STRUCTURAL_PROJECTION_FROZEN: PASS
SIZE_PROJECTION_FROZEN: PASS
DECISION_RULES_FROZEN: PASS
EXECUTION_ORDER_FROZEN: PASS
HOLDOUT_HARNESS_FROZEN: PASS
SELECTED_HOLDOUT_EXECUTED: NO
TIMING_PRIVACY: OPEN / NOT TESTED
PACKET_LEVEL_TIMING: OPEN
HARDWARE_TEE: NOT_TESTED
READY_FOR_INDEPENDENT_V10A_AUDIT: YES
```

This is not an overall GO and does not authorize V10B.

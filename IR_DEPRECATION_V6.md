# IR deprecation in V6

`CANONICAL_IR_DEPENDENCY = NONE`.

Frozen evidence remains immutable:

- IR-v1 static: 3,574/7,386 = 48.39%;
- IR-v1 fidelity: 54/72 = 75.0%;
- IR-v2: 72/72 development regression, not untouched holdout evidence;
- all corpus, classifier, semantic, and workflow artifacts remain historical.

`action_privacy_v6` imports no `agent_control_virtualization` or
`canonical_v3` module. The generic SimplePIR wrapper now imports historical
capsule adapters lazily, so raw-byte V6 retrieval does not load Control IR.
No source was deleted because prior results remain reproducible. Historical
entrypoints stay available but are not referenced by the canonical README or
V6 tests.

The active generality question is outbound action mediation coverage, not
whole-program compilation coverage. The 48.39% result is neither overwritten
nor reinterpreted.

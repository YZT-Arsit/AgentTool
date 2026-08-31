# V12 Timing Security Argument

For protected trajectories sharing one public profile, the target is observer-view indistinguishability:

```text
View_time(tau_0) ~= View_time(tau_1)
T_i = nominal_i + J_i
```

`nominal_i` is a deterministic public-profile value. `J_i` is realized execution and platform noise. The design target is that `J` is independent of the protected trajectory under the frozen passive-observer threat model. This is an empirical premise to be tested, not an already-proven fact.

The argument is conditional: if OHTTP cells are cryptographically indistinguishable; public cell identity, count, size, and order are fixed; each slot's content is logically committed without using private state arriving after its nominal cutoff; Registry queries occur on a fixed real-SimplePIR schedule; and realized scheduling noise is secret-independent, then the modeled Registry and Relay timing views reveal no protected trajectory information beyond the declared public profile.

Nominal lateness is observable evidence, not an automatic privacy failure or pass. A fixed transcript is necessary but insufficient. The decisive criterion is the predeclared best-attacker equivalence rule, with valid learnable positive controls.

This argument does not cover active scheduler manipulation, malicious hypervisors, packet-level timing, global Internet analysis, provider-invocation hiding from the provider, or hardware TEE behavior.

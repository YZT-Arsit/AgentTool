# V13B structural composition argument

This is an engineering security note, not manuscript text.

Let `C_t` be the planner candidate set, `E` the enterprise-deployed Agent
inventory, and `b_t = 1[C_t intersect E is nonempty]`. Let `View_str` be the
allowlisted structural projection of `(Q_PSI,Q_PIR,M)` with timing omitted.

For `b_t=1`, the trusted runtime performs real padded receiver-only PSI,
queries the existing SimplePIR padding row, and submits the enterprise target
through the common Trusted Gateway ingress. For `b_t=0`, it performs the same
PSI profile, queries the required real SimplePIR row, and submits the global
target through the same Gateway ingress.

Subject to receiver-only PSI privacy from a future vetted backend, existing
SimplePIR query privacy, protected TEE state, the fixed one-PSI-plus-one-PIR
profile, and the common Gateway boundary:

```text
View_str(b_t=0)  approximately_c  View_str(b_t=1)
```

The deterministic test instantiation checks exact byte/field equality of the
allowlisted structural projections. This is a contract test, not a statistical
attack experiment and not a substitute for cryptographic PSI.

The statement excludes realized timing and post-Gateway target observation.
If `O_agentcloud` can also observe the Gateway's downstream target connection
or enterprise Agent container/process identity, that deployment falls outside
the frozen observer boundary and the source/identity-hiding statement does not
apply.

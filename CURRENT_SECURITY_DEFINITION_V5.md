# Current security definition V5

For a fixed privacy profile and public configuration `Gamma`, compare legal
executions with the same public task class, horizon, frame bucket, session
policy, public outcome class, and profile-specific leakage.

`STRICT` leakage excludes payload, enterprise/external route, Agent identity,
handoff, action type, Tool identity, and external destination from the Agent
Cloud. `CONFIDENTIAL_ENTERPRISE` additionally reveals route class and may reveal
endpoint action class. `ENTERPRISE_EFFICIENT` also reveals configured coarse
Tool/action category. Cross-profile comparisons are undefined.

The intended property is:

```text
L_profile(tau0) = L_profile(tau1)
  => View_cloud^Gamma(tau0) ~=c View_cloud^Gamma(tau1)
```

`View_cloud` contains attestation/public profile records, fixed encrypted
envelopes, endpoints, count/order/size/session lifetime, and any declared
timing/resource fields. It excludes trusted TEE memory.

Current status: **NOT ESTABLISHED END TO END**. Functional local bootstrap,
verification, semantic fidelity, profile enforcement, and one development
Gateway workflow pass. Hardware attestation, rollback anchoring, live STRICT
route privacy, long-horizon whole-workflow structural/size privacy, timing, and
resource privacy remain open.

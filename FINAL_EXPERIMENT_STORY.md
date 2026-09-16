# Final evaluation story

## RQ1: Does OAE hide Agent access identity and access-pattern structure?

The final Agent-access channel uses real labeled APSI followed by real
SimplePIR in every public slot. V15E observes the exact serialized server-side
application-protocol objects without packet loss: 4,000 complete three-access
sessions, 12,000 logical accesses, and 16,000 complete APSI and SimplePIR
captures. The same-Agent ALL-view attack reaches AUC 0.487 (95% CI
[0.446, 0.526]); the two cross-session settings reach 0.519 and 0.472. Direct
AgentID controls reach 1.0 under the same splits, showing that the attack
pipeline recovers identity when it is exposed.

The direct four-class `AAA`/`ABA`/`AAB`/`ABC` task reaches 0.256 accuracy
(chance 0.25). Rare insertion and recurrence attacks remain near chance, but
the return-pattern task retains a small signal (AUC 0.551, p=0.0389).
Consequently, same-Agent, cross-session, ordering, recurrence, and rare-Agent
claims are supported under the declared observer and attacker suite; return-
pattern privacy is not established. Exact full-session structural projection
equality separately establishes that the fixed profile hides the number,
placement, and deployed/unprovisioned/idle type of logical accesses from the
permitted structural view.

## RQ2: Does OAE hide cloud-visible execution-trajectory structure?

The final Agent-access schedule and the frozen 521-cell Gateway profile produce
equal normalized structural projections across eight private-pattern classes.
The four-class execution-trajectory component composition reaches 0.2125
accuracy against 0.25 chance, while the matched unnormalized action-endpoint
control reaches 1.0. This supports the structural trajectory claim, with the
explicit limitation that the 0.2125 result is an exact final-component
composition rather than a fresh integrated 800-session campaign.

## RQ3: What timing leakage remains?

OAE's positive guarantee is structural, not realized timing
indistinguishability. Application-protocol timing distinguishes provisioned,
unprovisioned, and idle Agent-access branches with 0.663 accuracy (95% CI
[0.610, 0.717], p<0.0001). Across all four final Gateway timing settings, the
largest held-out AUC is 0.645 for Microsoft Tool versus Agent-as-Tool (95% CI
[0.465, 0.818], p=0.0612). The complete timing panel retains all four settings
and their matched one-sided component controls. Agent-access and Gateway
realized timing privacy are therefore not established.

## RQ4: Is OAE practical at enterprise-store scale?

The final system uses a 100,000-record store of schema-valid
ProvisionedAgentArtifactV1 records with real APSI and real SimplePIR. A warm
scale sweep covers 1K, 10K, 50K, and 100K records with 30 queries per point; at
100K, combined pipelined access is 57.173 ms p50 and 61.818 ms p95. The corpus
is not described as 100K independently sourced real-world Agents.

Both supported frameworks complete all 240 non-idle semantic executions, and
all 280 sessions conform to the public profile. Overflow, silent loss,
retrieval failure, loader failure, and dummy heavy Agent/LLM/Tool execution are
all zero. End-to-end retrieval latency is 771.729/7466.234 ms p50/p95 and task
latency is 5002.551/14880.534 ms.

A new matched native baseline covers the same five semantic workload families
for both frameworks, with 10 measured native runs per coordinate and no
failures. Native p50 task latency ranges from 0.417 to 6.916 ms, whereas OAE
p50 latency ranges from 1168.260 to 7292.604 ms. The resulting large slowdown
ratios reflect a deterministic local semantic fixture whose native execution
is extremely short; per-workload absolute additive latency is the more useful
paper comparison. Communication is 9.903 MiB per base public profile and
11.318 MiB per measured execution for the observed workload mix with
continuation profiles.

## Claim boundary

The evidence supports the frozen cryptographic and structural design under the
declared cloud-visible application-protocol observer. It does not establish
packet-level, microarchitectural, cross-provider, or realized-timing privacy.
The return-pattern and timing residuals are final reported results, not triggers
for further redesign.

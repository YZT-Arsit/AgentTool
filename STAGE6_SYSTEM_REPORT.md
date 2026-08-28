# Stage-6 Enterprise Mediation System Report

## 1. Executive system decision

**CONFIGURATION-DEPENDENT SYSTEM DESIGN**

The enterprise semantics materially change Stage 5's ranking. HYBRID-PH is the
steady-state bandwidth winner and has the lowest p95 in LAN/cloud, while
HYBRID-P is lowest in the DC run; neither dominates when devices have unseen global history:
sync traffic and local cache size grow with cross-device updates. HYBRID-P is
the robust large/churning-history choice. Fixed canonical modular remains a
meaningful deployment-specific point because it preserves separately owned
authoritative services without placing policy or global audit copies on
employee devices. Unified does not win the actual-wire comparison.

## 2. What changed from Stage 5

Stage 5 credited Hybrid with locally held permission/history state. Stage 6
keeps all three state categories authoritative remotely and charges Hybrid for
per-action policy validation, ordered history synchronization, multi-device
copies, administrator changes, and recovery-relevant cache growth. It replaces
single-process function timing with spawned processes, TCP framing, actual JSON
serialization, real ciphertext-padding transfer, and application-layer network
emulation.

The privacy phenomenon and claim are frozen; no new action was introduced to
strengthen it.

## 3. Concrete enterprise deployment

The local system implements an untrusted planner, trusted mediator, separately
authoritative PrivateData/Permission/DisclosureLog services, a unified service
for that baseline, an idempotent mock email sink, and a host observer. Multiple
logical employees and two devices share permission and audit authority. The
primary task is the same synthetic `SEND_MESSAGE` resolution of Project Aurora
handles.

All data, addresses, policy values, documents, users, messages, and effects are
synthetic. No external API, real account, credential, or network is accessed.

## 4. Process architecture

The default cluster starts 13 distinct processes: planner, observer, five
services, and six architecture-specific mediators. All component calls cross
localhost TCP with four-byte length-prefixed canonical JSON. PID and socket
tests confirm that the boundaries are real. `SYSTEM_ARCHITECTURE.md` documents
the process diagram, message sequence, state ownership, ORAM placement, and
observer view.

## 5. Trust model

The planner and infrastructure metadata observer are untrusted. Mediators and
service internals are trusted for this experiment. Protected service bodies use
a local confidentiality abstraction; the observer sees endpoint, operation
class, serialized sizes, timing, connection reuse, and logical path-transfer
size. Only the mediator and authorized mock tool materialize final plaintext.
Tool identity and authorized disclosure are public.

## 6. Authoritative-state semantics

Permission reads are current and linearizable at the permission request.
Revocation acknowledged before an action begins is visible on that action. Log
appends are ordered, locked, and idempotent by tenant/request ID. A device
starting after another device's acknowledged append observes it. Every Hybrid
action performs remote policy validation; every HYBRID-PH action additionally
synchronizes all events since its local version. See `CONSISTENCY_MODEL.md` for
the precise race and retry boundaries.

## 7. Baselines

The ENTERPRISE-DC primary table reports measured application wire and
end-to-end local-process latency. Trusted bytes are logical map/stash/cache
accounting, not RSS.

| Architecture | Privacy | Revocation | Audit | Trusted KiB | Wire KiB/action | p95 ms | Requests/action |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DIRECT-MODULAR | fail | pass | pass | 0.0 | 5.0 | 89.41 | 4.38 |
| INDEPENDENT-MODULAR-ORAM | fail | pass | pass | 58.3 | 286.1 | 97.18 | 4.75 |
| FIXED-CANONICAL-MODULAR | pass | pass | pass | 58.3 | 292.9 | 96.70 | 5.00 |
| UNIFIED-ORAM | pass | pass | pass | 58.0 | 604.3 | 133.58 | 3.00 |
| HYBRID-P | pass | pass | pass | 54.1 | 281.6 | 88.81 | 5.00 |
| HYBRID-PH | pass | pass | pass | 39.5 | 229.3 | 93.27 | 5.00 |

Direct and independent modular are leakage references and are excluded from
the primary Pareto set.

## 8. Functional equivalence

All architectures produce the same ALLOW result, sanitized sent status,
authoritative disclosure append, and invalid-action DENY. Retrying one request
ID produces one tool effect and one log entry. The privacy layer does not delete
recipient/document resolution or audit work.

## 9. Authorization equivalence

Each baseline was tested with allowed, revoked, newly allowed, unauthorized,
and syntactically invalid actions. All produced the same authorization result.
The planner response was serialized and checked for recipient email, document
content/title, and hidden branch fields; none were present.

## 10. Revocation experiment

The administrator update is acknowledged before the post-revocation action.
Every protected architecture denied it, with zero delayed subsequent actions.

| Architecture | Extra freshness RTT | Extra validation bytes | Observed deny latency | Correct? |
| --- | ---: | ---: | ---: | ---: |
| Fixed canonical | 0 | 0 | 24.27 ms | pass |
| Unified | 0 | 0 | 53.43 ms | pass |
| HYBRID-P | 1 | 560 B | 48.36 ms | pass |
| HYBRID-PH | 1 | 560 B | 46.92 ms | pass |

The wall times are one LOCAL-LAN observation and are not comparative latency
estimates. “Extra” means beyond the architecture's normal authoritative work;
fixed/unified already read permission remotely. DENY→ALLOW was visible on the
next action for all baselines.

## 11. Cross-device disclosure-history experiment

Device A disclosed, its append completed, and device B then acted. The
authoritative version reached two for every architecture.

| Architecture | A visible to B | Explicit sync bytes | Sync RTT | Correct? |
| --- | ---: | ---: | ---: | ---: |
| Fixed canonical | yes | 0 | 0 | pass |
| Unified | yes | 0 | 0 | pass |
| HYBRID-P | yes | 0 | 0 | pass |
| HYBRID-PH | yes | 1,060 B | 1 | pass |

The first three consult authoritative state directly; only HYBRID-PH maintains
a local audit copy and therefore requires a delta synchronization.

## 12. Concurrency correctness

Thirty-two concurrent fixed-canonical actions shared recipient, document,
permission, and log. All 32 were authorized, the authoritative version was 32,
lost updates were zero, and duplicate unauthorized effects were zero. Service
locks supply per-service linearizability; this is not a distributed transaction
across policy, tool, and log.

## 13. Mediation privacy sanity check

The balanced 24-episode strongest structural probe gave:

| Architecture | AUC | Accuracy | Shuffled AUC | Decision |
| --- | ---: | ---: | ---: | --- |
| Direct modular | 1.000 | 1.000 | 0.500 | fail/reference |
| Independent modular ORAM | 1.000 | 1.000 | 0.500 | fail/reference |
| Fixed canonical | 0.500 | 0.500 | 0.500 | pass |
| Unified | 0.500 | 0.500 | 0.500 | pass |
| HYBRID-P | 0.500 | 0.500 | 0.500 | pass |
| HYBRID-PH | 0.500 | 0.500 | 0.500 | pass |

This is a narrow frozen-channel sanity check, not a new leakage-discovery suite.

## 14. Actual wire traffic

ENTERPRISE-DC mean bytes by endpoint are:

| Architecture | Private | Permission | History | Unified | Tool | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed canonical | 231,218 | 11,908 | 54,904 | 0 | 1,864 | 299,894 |
| Unified | 0 | 0 | 0 | 616,928 | 1,836 | 618,764 |
| HYBRID-P | 231,178 | 600 | 54,804 | 0 | 1,824 | 288,406 |
| HYBRID-PH | 231,178 | 600 | 1,178 | 0 | 1,828 | 234,784 |

Totals include actual request and response JSON sent to authoritative services
and the tool. Of canonical's total, 299,854 B is JSON payload and 40 B is
length framing. Planner→mediator traffic is accounted separately (1,681 B for
canonical, 1,305 B unified, 1,638 B HYBRID-P, and 1,635 B HYBRID-PH). TCP/IP
headers are outside application visibility. `logical_oram_bytes` remains a
separate column in the CSV.

## 15. Actual process latency

| Architecture | Mean | Median | p95 | p99 | Profile |
| --- | ---: | ---: | ---: | ---: | --- |
| Fixed canonical | 77.66 | 69.81 | 96.70 | 96.70 | ENTERPRISE-DC |
| Unified | 111.66 | 115.49 | 133.58 | 133.58 | ENTERPRISE-DC |
| HYBRID-P | 72.90 | 65.42 | 88.81 | 88.81 | ENTERPRISE-DC |
| HYBRID-PH | 69.87 | 59.61 | 93.27 | 93.27 | ENTERPRISE-DC |

Sample counts are 10/8/5 per architecture for LAN/DC/cloud. Consequently p95
and p99 often select the same tail sample; they should be treated as prototype
observations, not production SLO estimates.

Mean measured server dispatch compute attributed to ORAM construction was only
0.40–0.50 ms; serialization, socket copying, emulated transfer, and OS
scheduling dominate. HYBRID-P validation averaged 13.05 ms in the DC run;
HYBRID-PH validation/sync averaged 8.87/16.39 ms. These noisy concurrent-preflight
breakdowns are diagnostic rather than additive critical paths.

## 16. Network-profile emulation

| Architecture | LAN p95 | DC p95 | Cloud p95 | Mean wire KiB |
| --- | ---: | ---: | ---: | ---: |
| Fixed canonical | 82.40 | 96.70 | 201.20 | 292.8–292.9 |
| Unified | 84.56 | 133.58 | 243.52 | 604.2–604.3 |
| HYBRID-P | 82.02 | 88.81 | 185.65 | 281.6 |
| HYBRID-PH | 81.68 | 93.27 | 182.96 | 229.2–229.3 |

The profiles are emulated locally at 0.5/2/20-ms RTT and
1,000/200/50-Mb/s. OS scheduling noise explains non-monotonic LAN/DC samples;
the cloud profile shows the expected wire/RTT ordering.

## 17. Trusted-state cost

At MEDIUM and one active device, trusted logical bytes are 59,648 fixed,
59,392 unified, 55,424 HYBRID-P, and 40,448 HYBRID-PH. The latter is initially
small because only observed history is cached, not the entire configured log.
At 128 new devices in SMALL, HYBRID-P caches 21,632 B while HYBRID-PH reaches
2,279,808 B because every device synchronizes the global prefix it has not seen.

All architectures still retain the complete authoritative remote payload. This
removes Stage 5's implied server-storage saving for Hybrid.

## 18. Hybrid freshness cost

HYBRID-P pays one 560-B version validation each action and has no lease/stale
window. HYBRID-PH pays that validation plus one history sync. With 10/100/1,000
unseen entries, HYBRID-PH total wire is 232.4/262.0/559.7 KiB, sync wire is
4.0/33.6/331.3 KiB, and cache size is 4,096/30,080/286,464 B. HYBRID-P remains
about 281.4 KiB across the growth sweep.

At rare/moderate/frequent policy-update rates (1/5/20 revoke-allow cycles per
100 actions), every Hybrid still validates once/action. Amortized administrator
traffic is small relative to ORAM wire; update frequency does not create an
unsafe stale window or materially change the bandwidth ranking.

## 19. Unified deployment implications

Unified reduces MEDIUM service requests from five to three, but its common tree
makes serialized ORAM transfer 604 KiB/action—over twice fixed modular. In the
equal-record Stage-6 case it is still larger: 2,092 KiB versus 1,848 KiB actual
wire. Stage 6 resolves both recipient and document and performs both history
consultation and update, so the previous Stage-4 three-path unified advantage
does not survive these enterprise semantics.

Under strong heterogeneity, unified is 2,892 KiB versus 1,134 KiB fixed. It also
requires merging separately owned databases and adopting a common tagged record
layout. Coupling is documented separately and is not folded into latency.

## 20. Modular deployment implications

Fixed canonical preserves the three authoritative service boundaries and uses
independently sized records/paths. It has no client policy or audit cache and no
cache recovery protocol. It performs more RPCs than unified and more wire than
both hybrids at steady state. Its meaningful region is therefore deployment
preservation and bounded trusted-client state, not universal performance.

As in Stage 5, the schema compiler saved no work over the handwritten fixed
schedule and is not claimed as an optimizer contribution.

## 21. Pareto analysis

No valid architecture dominates all dimensions:

- HYBRID-PH: minimum steady-state wire and primary p95; worst cache/sync growth
  under many devices or unseen events.
- HYBRID-P: slightly less wire than fixed, bounded permission cache, and no
  history synchronization; preferred under large/churning global history.
- Fixed canonical: separate authority/ownership preservation and no employee
  policy/audit cache, at modest additional wire.
- Unified: fewest service requests, but highest actual wire, common-layout
  coupling, and no measured regime win.

Thus the quantitative Pareto set is HYBRID-PH/HYBRID-P; fixed canonical joins
when deployment coupling and client authoritative-state placement are included.
Unified is not Pareto-optimal in the evaluated configurations, although another
wire representation or existing consolidation could change that.

## 22. Falsification result

**Does correctly synchronized HYBRID-PH still dominate? CONFIGURATION
DEPENDENT.** It wins clean steady state but loses its bounded-state/bandwidth
advantage as unseen global history grows.

**Does Unified remain cheaper? NO.** Actual bytes and the required five logical
record paths remove the equal-record advantage and worsen heterogeneity.

**Does fixed canonical occupy a meaningful region? YES, but only through
deployment preservation and avoidance of client policy/audit caches.** It is not
the performance winner and not universally preferred.

The original method is therefore falsified as a universal or primary systems
winner, while retained as a deployment-specific design point.

## 23. Scientific limitations

- Local XOR/base64 protection and ORAM ciphertext padding are engineering
  abstractions, not authenticated encryption or production ORAM.
- Services are localhost processes on one machine; no real WAN, disks, TLS,
  database engine, key service, or production serializer is measured.
- ORAM path content and eviction are not implemented cryptographically.
- Hybrid cache durability, sealing, rollback protection, recovery, and device
  loss are not implemented; these would further weaken Hybrid.
- Unified packing and a production common schema are not implemented; a better
  representation could reduce its wire.
- Permission check and tool effect are not one distributed transaction.
- Tail latency samples are deliberately small to keep validation rapid.
- The privacy check covers the frozen structural channel, not comprehensive
  timing/size leakage.
- State counts and network profiles are synthetic experiment parameters.

## 24. Recommended architecture after Stage 6

Default to HYBRID-P for shared enterprise deployments with large or active
global audit histories. Use HYBRID-PH only when history is bounded/low-churn and
trusted cache persistence/recovery is acceptable. Use fixed canonical modular
when preserving existing authoritative service ownership and avoiding policy or
audit copies on employee devices is a hard constraint. Do not select Unified on
the current wire results alone.

### Mandatory final questions

| Question | Answer |
| --- | --- |
| Q1. Does HYBRID-PH remain cheapest with equivalent revocation/history semantics? | **CONFIGURATION DEPENDENT** |
| Q2. Does HYBRID-P remain cheapest in the large regime after freshness validation? | **CONFIGURATION DEPENDENT**—HYBRID-PH wins low-churn steady state; HYBRID-P wins growing/unseen history |
| Q3. Is Unified cheaper than modular for equal records using actual wire bytes? | **NO** |
| Q4. Does Unified retain an advantage under strong heterogeneity? | **NO** |
| Q5. Does fixed canonical occupy a meaningful Pareto region? | **YES**, when deployment preservation is a dimension |
| Q6. Does modularity provide a measurable deployment-preservation advantage? | **QUALITATIVE ONLY** |
| Q7. Can authoritative permission remain purely local without freshness checks? | **NO** |
| Q8. Can authoritative DisclosureLog remain purely local with multiple devices? | **NO** |
| Q9. Do enterprise consistency semantics materially change Stage 5's ranking? | **YES** |
| Q10. Is canonical modular still justified as a method contribution? | **ONLY AS A DEPLOYMENT-SPECIFIC DESIGN POINT** |
| Q11. Is the research problem still supported? | **YES**, within the frozen narrow boundary |
| Q12. Is another synthetic privacy validation required? | **NO** |

Implementation and empirical trade-off should now be frozen. The next useful
step is a production feasibility/security audit of authenticated storage,
persistent cache recovery, and failure handling—not another synthetic leakage
scenario.

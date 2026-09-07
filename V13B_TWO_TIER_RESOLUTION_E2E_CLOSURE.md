# V13B two-tier resolution threat-model and E2E closure

This closure adds a narrow composition layer from planner candidates through
the V13 resolver to the frozen common Gateway submission ABI. It changes no
V4R8 timing, PIR, Gateway, Relay, provider-timeout, or bounded-liveness code.

## Required report

| Field | Result |
|---|---|
| `BASE_V13` | `046dd5e87ed9bc3bb40be6304d062417a73e2549` |
| `BASE_V4R8_RUNTIME` | `63319014f560f46e2a46dd140f53551e43c27e0d` |
| `THREAT_MODEL_PRIMARY_ADVERSARY` | `UNTRUSTED_AGENT_CLOUD_PROVIDER` |
| `PUBLIC_VIEW` | `Q_PSI`, `Q_PIR`, `M` |
| `NEW_SECRET_BRANCH` | `ENTERPRISE_HIT_VS_LIBRARY_FALLBACK` |
| `PSI_VARIANT_REQUIRED` | `RECEIVER_ONLY_PSI_OR_PRIVATE_SET_MEMBERSHIP` |
| `PSI_CRYPTO_BACKEND` | `NOT_CRYPTOGRAPHICALLY_INSTANTIATED` |
| `CANDIDATE_K` | `8` |
| `ENTERPRISE_PADDED_BOUND` | `1024` |
| `ENTERPRISE_AGENT_THROUGH_COMMON_GATEWAY` | `PASS` |
| `GLOBAL_AGENT_THROUGH_COMMON_GATEWAY` | `PASS` |
| `DIRECT_TEE_TO_ENTERPRISE_AGENT_CONNECTIONS` | `0` |
| `ENTERPRISE_AGENT_EXECUTION_IDENTITY_LEAK` | `OUTSIDE_FROZEN_OBSERVER_AFTER_COMMON_GATEWAY` |
| `FIXED_PSI_SLOT` | `PASS` |
| `FIXED_PIR_SLOT` | `PASS` |
| `HIT_PIR` | `PADDING` |
| `MISS_PIR` | `REAL` |
| `HIT_FALLBACK_STRUCTURAL_EQUIVALENCE` | `PASS` |
| `OPENAI_INTEGRATION` | `4/4 PASS` |
| `MICROSOFT_INTEGRATION` | `4/4 PASS` |
| `CORRECTNESS_TESTS` | V13B `14/14 PASS`; targeted regression `69 PASS`, `0 FAIL`, `1` platform skip |
| `PROTECTED_V4R8_RUNTIME_DIFF` | `NONE` |
| `GATEWAY_TIMING_PROFILE_DIFF` | `NONE` |
| `NEW_PRIVACY_ATTACK_EXPERIMENTS` | `0` |
| `PSI_MICROBENCHMARK` | `NOT_RUN` |
| `EXISTING_UTILITY_INCLUDES_PSI` | `NO` |
| `DESIGN_CLOSURE` | `PASS` under the frozen observer boundary |
| `PAPER_FILES_MODIFIED` | `NO` |

## Integration result

`ExistingGatewayControlChannelAdapter` implements both the V13 trusted handoff
and the exact existing `SUBMIT_RESOLVED_ACTION` control ingress. The two source
classes stage different descriptors and route handles only as trusted private
state. Both serialize the same control-message type on the same existing
Gateway stream; neither adds a source-specific RPC, connection, endpoint, port,
or direct TEE-to-Agent link.

OpenAI Agents SDK and Microsoft Agent Framework each completed singleton hit,
multi-candidate hit, singleton fallback, and multi-candidate fallback. Every
case selected the expected descriptor/source, produced the exact semantic
result, consumed one PSI slot and one PIR slot, used padding PIR on hit and real
PIR on miss, entered the common Gateway exactly once, and recorded no silent
loss. The eight executions were functional/structural tests, with zero retries.

Paired hit/fallback projections for both frameworks were byte-identical after
applying the explicit `(Q_PSI,Q_PIR,M)` allowlist. Candidate IDs, intersection,
PIR real/padding choice, descriptors, route handles, source class, operation ID,
and private execution handles were absent.

## Threat-model boundary

The `PASS` verdict is conditional on the already-frozen common-Gateway observer
boundary. The existing Gateway makes a private downstream HTTP request after
its common ingress. The canonical threat model excludes that downstream
traffic from `O_agentcloud`; therefore the mandatory classification is
`OUTSIDE_FROZEN_OBSERVER_AFTER_COMMON_GATEWAY`, not an assertion that no
physical egress exists.

If the same infrastructure operator can observe the Gateway's downstream
endpoint, connection, process, container, or route identity, this observer
separation fails and enterprise-Agent execution identity is exposed. This
closure does not hide that stronger view and must not be cited for such a
deployment.

## Explicit non-results

The PSI backend remains a deterministic functional mock. No PSI latency or
bandwidth was measured, and prior OAE utility numbers do not include PSI. No
timing/linkability classifier, AUC, bootstrap, randomization, smoke campaign,
P20/P25, confirmatory run, or holdout was executed. Realized timing
indistinguishability is not part of the structural composition statement.

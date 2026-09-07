# V13B threat-model and execution-identity audit

This is engineering evidence, not manuscript text. It aligns the two-tier
enterprise-Agent scenario with the canonical OAE observer without weakening or
renaming that observer.

## Deployment and adversary

The primary adversary remains the **untrusted / honest-but-curious Agent-cloud
provider** (`O_agentcloud`). The Enterprise Agent Directory is outside the
protected runtime/TEE, and the enterprise-deployed Agents and global Agent
library reside in cloud infrastructure. Cross-provider collusion remains out of
scope.

The observer view is extended from `(Q,M)` to:

```text
V = (Q_PSI, Q_PIR, M)
```

- `Q_PSI` is the public transcript and profile of private enterprise-Agent
  availability resolution.
- `Q_PIR` is the public SimplePIR transcript for the global Agent Library.
- `M` is the existing application-visible common-Gateway metadata, including
  the public profile, endpoint class, size, count, direction, and timestamps
  already allowed by the frozen model.

The additional protected bit is `b_t = 1[C_t intersect E is nonempty]`.
Candidate IDs, the intersection, selected Agent, source class, and private
execution handle remain protected. This statement does not claim realized
timing indistinguishability.

## Receiver-only PSI requirement

The required primitive is receiver-only PSI or private set membership. Its
output recipient is `TRUSTED_RUNTIME_ONLY`. The Enterprise Agent Directory is
not authorized to learn the candidate set, intersection, selected Agent, or
branch bit beyond the K=8/E=1024 public profile.

The deterministic V13 mock still exposes raw values inside the functional test
process and remains `NOT_CRYPTOGRAPHICALLY_INSTANTIATED`. It is neither a PSI
privacy implementation nor deployable evidence.

## Common Gateway audit

The frozen online runtime submits every resolved action through the private
`SUBMIT_RESOLVED_ACTION` control ingress (`v11_online/session.py:1161-1168`),
which the Go Gateway accepts at
`common_action_gateway_v2/canonicalv9/online.go:415`. V13B adds a narrow adapter
that stages either source class as private trusted state and writes that same
message on the already-established Gateway control stream. It creates no HTTP
client, socket, endpoint, port, RPC variant, or TEE-to-Agent connection.

The route handle, source class, descriptor, and execution handle are excluded
from the structural observer projection. They are consumed only after the
common Gateway ingress. The Gateway's existing provider path resolves its
private route and performs downstream HTTP execution at
`common_action_gateway_v2/canonicalv9/runner.go:586-608`; no part of that frozen
path was changed.

## Mandatory execution-identity classification

```text
ENTERPRISE_AGENT_EXECUTION_IDENTITY_LEAK =
    OUTSIDE_FROZEN_OBSERVER_AFTER_COMMON_GATEWAY
```

This classification follows the active threat model, which treats the Gateway
as trusted and states that `O_agentcloud` sees only the common Gateway endpoint,
while independently observed downstream-provider traffic belongs to a separate
observer (`CANONICAL_THREAT_MODEL_V3.md:41-46` and
`CURRENT_SECURITY_ASSUMPTIONS.md:19-20`). The V13B composition therefore has
zero direct TEE-to-enterprise-Agent connections and exposes one common Gateway
ingress under that frozen boundary.

This boundary is a real deployment restriction, not a claim that a Gateway
magically hides its egress from its infrastructure operator. If the same cloud
operator can observe the post-Gateway endpoint, connection, process, container,
or route identity, the frozen separation is false and enterprise-Agent identity
is exposed. Such a deployment is outside this closure and would require a
stronger dispatcher/anonymity/TEE placement assumption before making the same
identity-hiding claim.

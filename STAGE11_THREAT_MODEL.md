# Stage-11 Threat Model — historical, dispatch design superseded

Any full-cover or ORAM-backed Agent invocation discussion below is retained as
historical analysis, not an active design or privacy claim.

## 1. Frozen confidentiality boundary

The project remains benign, defensive, local, and synthetic. The cloud planner is untrusted. The trusted mediator/private resolver, local approval UI, ORAM/PIR client state, and synthetic effect gate are trusted. Persistent protected state is authoritative. Fine-grained microarchitectural leakage, malicious cryptographic endpoints, and real network/service attacks remain outside scope.

Stage 11 expands the structural observer to message size and scheduled timing. It does not silently make every party mutually distrustful or colluding.

## 2. Values and leakage classes

Protected where relevant:

- private user/security state;
- concrete specialist-agent identity and registry index;
- approval, authorization, provenance, and history state;
- internal branch, operation order, round count, approval/consent occurrence, and retry/resume occurrence;
- internal message-size sequence and round timing/cadence.

Allowed/public within the main class:

- public task projection and semantic capability class;
- runtime/framework and public deployment configuration;
- public horizon `H`, cadence `Delta`, size bucket/bound `B`, and approval window `W`;
- complete observer-visible final-effect projection;
- public success/failure class and overflow policy.

The successful same-effect experiment never compares an ALLOW trace with a DENY trace.

## 3. Observer-specific goals

| Observer | Sees | Should remain hidden | Unavoidable/allowed leakage |
|---|---|---|---|
| A. Decision LLM/planner provider | Public task projection, capability catalog/schema, opaque capability handle, sanitized result | Concrete agent/provider/endpoint, credentials, private authorization/provenance, approval/retry path | Semantic capability and public final effect |
| B. Agent registry/storage provider | Physical storage/PIR requests, sizes, cadence, database-size class | Registry index, concrete record chosen, repeated logical address | Declared database size/access budget |
| C. Infrastructure/network observer | Destination/relay slots, message sizes, cadence, bursts, public commit | Selected concrete endpoint, internal round/branch, approval/retry occurrence | Public endpoints contacted by the chosen dispatch design; full cover contacts all slots |
| D. Specialist-agent provider | Its incoming envelope and plaintext real request after authorization/decryption | Other private mediator state, unnecessary user data, why other agents were/weren't selected | Whether it itself received authorized real work; this cannot be hidden from it under direct execution |
| E. External tool provider | The one authorized real effect and public operation ID/projection | Internal agent choice and mediation path, unrelated private state | Full visible effect projection and public outcome |
| F. Trusted mediator/private resolver | Capability, concrete index/record, authorization, provenance, keys, real/dummy state | Nothing required by this model | It is trusted and is the principal confidentiality concentration point |

## 4. Non-colluding primary models

Three distinct games are used rather than one ambiguous “host”:

1. **Registry privacy:** observer B should not distinguish which record was retrieved. PIR/ORAM can address this.
2. **Dispatch privacy:** observer C should not distinguish which concrete endpoint is real. Direct dispatch fails; R3 full cover can address it at `Theta(N)` fanout.
3. **Adaptive mediation privacy:** the mediation/storage observer should not distinguish private approval/provenance states inside one leakage class. M3 uses bounded slots, ORAM-backed state access, fixed size, and fixed cadence.

No result from one game is reported as a result for another.

## 5. Collusion audit

| Collusion | Result |
|---|---|
| A + B | Opaque capability plus resolver-side PIR can still protect `i` if neither receives resolver secrets and the capability does not uniquely map publicly to one agent. If the public catalog has a one-to-one capability mapping, identity is already leaked by allowed capability. |
| B + C | PIR/ORAM query privacy does not help if C sees a unique direct endpoint. Full cover/shared relay is still required. |
| C + selected D | Selected identity is known: D knows it processed real work and can identify itself to C. Full-cover identity privacy is impossible against this collusion under direct decryption. |
| A + F | All routing and mediation secrets are exposed because F is the trusted resolver. This is outside the confidentiality model. |
| B + F | Registry privacy collapses because the PIR/ORAM client knows `i`. |
| D + E | They may link a specialist request to the final effect. The project does not promise to hide the real effect from its provider. |
| All observers | The proposed guarantees are impossible; the trusted-mediator boundary is eliminated. |

The primary theorem therefore quantifies a named observer, not a universal colluding adversary.

## 6. Capability versus identity

The coherent planner contract is:

```text
public task -> semantic capability class -> opaque handle h
trusted resolver: h + private policy/configuration -> concrete agent index i
```

This protects concrete identity only if a capability class contains at least two plausible concrete agents and public context does not uniquely determine the mapping. The capability-to-index policy is trusted/private. If `calendar-management` publicly means exactly `Agent_17`, no cryptographic registry lookup can undo that semantic disclosure.

## 7. Failure and effect boundary

No cover operation may cross the external effect gate. Dummy agent envelopes authenticate as internal no-ops. The selected real envelope must still pass authorization and provenance checks. DENY remains DENY. Horizon overflow, late approval after `W`, malformed ciphertext, or inability to establish fresh policy state fails closed before an effect.

## 8. Explicit exclusions

- protecting concrete identity from the selected specialist itself;
- collusion involving the trusted mediator/private resolver;
- unbounded or fine-grained continuous-time privacy outside public epochs;
- CPU/cache/power side channels;
- hiding public success/failure or the complete external effect projection;
- production anonymity-network, PIR, MPC, or FHE implementation security.

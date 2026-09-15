# V15A public Agent-access profile audit

## Mechanical result

`SESSION_LEVEL_AGENT_ACCESS_PRIVACY = NOT_IMPLEMENTED` in V14.

V14 proves that one explicitly invoked access has the same public APSI and
SimplePIR shape for provisioned, unprovisioned, and idle cases. It does not
own a session clock and does not issue access operations at every public
opportunity. Therefore the per-slot equality must not be described as a
complete fixed session schedule.

## V14 call path

- `v14_provisioned_agents/resolution.py:101-108`: `resolve(agent_id)` creates an
  operation only when called and immediately performs the APSI query.
- `v14_provisioned_agents/resolution.py:110,121,126`: the SimplePIR query is
  executed synchronously after that APSI result.
- `v14_provisioned_agents/resolution.py:134`: a causal Agent-to-Agent request
  recursively invokes `resolve(child_id)` immediately. There is no private
  request queue or public eligibility cutoff.
- `scripts/run_v14_preprovisioned_agent_closure.py:257`: the V14 functional
  harness directly calls `resolver.resolve(agent_id)` for each selected test
  case. An idle operation exists only when the harness explicitly passes
  `None`.

No V14 code defines a session-level `R_A`, `Delta_A`, `H_A`, public clock,
admission queue, or bounded overflow state. Operationally, V14 executes only
logical/test-requested slots.

## Nearest pre-existing public profile

The frozen V4R8 profile contains a Registry/SimplePIR schedule, not an
implemented V14 APSI+PIR schedule:

- `v12_timing/profile.py:13-17`: public epoch 6000 ms, initial lead 25 ms,
  maximum real Agent resolutions 6, and the historical dummy descriptor row.
- `v12_timing/profile.py:157-158`: `Q = epoch / period`.
- `v12_timing/profile.py:442-453`: validation freezes maximum real resolutions
  to 6 and the initial lead to 25 ms.
- `v12_timing/profile.py:658-673`: V4R8 fixes the Registry period to 60 ms.

Applying that nearest historical schedule as the **candidate under test** gives:

| Field | Audited result |
|---|---:|
| Candidate `R_A` | 100 public opportunities |
| Candidate `Delta_A` | 60 ms |
| Candidate `H_A` | 6000 ms public epoch |
| Initial lead | 25 ms |
| Candidate maximum admitted real resolutions | 6 |
| Last scheduled opportunity | 5965 ms from session origin |

These values are not silently promoted to a V15 production profile. They are
only the current-profile feasibility target required by this stage.

## Capacity interaction

The candidate permits at most six admitted real Agent resolutions. V14 itself
does not enforce that bound and can recurse immediately on every sub-Agent ID.
A future scheduler must place newly created Agent-to-Agent requests in a
trusted queue and either admit them at a remaining public opportunity or emit
an explicit `AGENT_ACCESS_NOT_ADMITTED` state after the fixed capacity/horizon.

`V14_PREVIOUSLY_EXECUTED_ONLY_LOGICAL_SLOTS = YES`.


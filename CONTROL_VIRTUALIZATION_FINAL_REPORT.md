# Agent control virtualization feasibility report

## Decision

**CONDITIONAL_GO**

The structural hypothesis survived: 95.3% of audited real-framework control
behaviors were compiled or assigned to a shared primitive; logical handoff kept
the same physical executor; a 100,000-row capsule registry was actually built;
and the common-executor trace was exactly equal across targets with one real and
zero dummy heavy operations.

The full privacy hypothesis did not yet survive end to end. The only integrated
lookup is a mock that exposes the target index, and the fixed transition scan is
not secure computation. Therefore this stage cannot claim
`View_cloud(A_i) ~= View_cloud(A_j)` for the complete system.

## Architecture and IR

The private unit is a fixed 1,024-byte capsule of at most 30 transition rows.
It stores instruction/tool/handoff handles and control state, while model and
Tool computation remain shared heavy primitives. `HANDOFF` changes a private
logical identifier and re-enters `AgentControlExecutor`; the host never sees a
new named executor in the tested boundary.

## Real-framework audit

Native OpenAI Agents SDK and Microsoft Agent Framework objects yielded 81 of 85
compiled-or-shared behaviors across nine workloads and 22 Agents. Dynamic
callbacks, arbitrary conditional predicates, and parallel fan-out account for
the four unsupported behaviors. This supports a framework-native declarative
subset, not arbitrary Python Agents.

## Scale and cost

The experiment allocated 1.024 MB, 10.24 MB, and 102.4 MB registries at
N=1K/10K/100K. At 100K, direct mock lookup averaged 0.494 us and the fixed
control scan about 0.590 us. These are architecture-plumbing measurements, not
PIR performance. Four 1,024-byte request/response pairs add 8,192 bytes. The
execution invariant was one real heavy operation and zero dummy heavy
operations.

## Privacy controls

Direct named execution gave top-1 accuracy 1.0. Visible 8-cover reduced a
single-call posterior only to 1/8 and repeated-set intersection identified the
target essentially perfectly after two to four calls. The common executor gave
exact trace equality and the N=1,000 structural chance baseline (top-1 0.001),
but including the mock lookup restored top-1 1.0.

## Three strongest reasons for the decision

1. Real-framework coverage exceeds the 80% gate and logical handoff works
   without named reactivation.
2. The 100K control registry and one-heavy-operation execution model are
   operationally small and runnable.
3. A real single-server PIR and secure control-step backend are missing, so the
   full-domain privacy goal is not yet demonstrated; live timing and final Tool
   destination privacy also remain outside the validated boundary.

The next experiment should integrate one audited real PIR implementation at
100K fixed 1,024-byte rows and measure its preprocessing, client hint, online
bandwidth, CPU, memory, and latency. If that integration is infeasible, the
correct final result is `NO_GO`.

# V15B workload-driven Agent-access profile candidates

All candidates use the same measured real wire cost (2,351,400 bytes per public PSI+PIR slot), the selected 350 ms conservative cadence, a dummy-PIR bootstrap in slot 0, and a final dummy-PSI drain. `R_A` is the total public slot count; maximum early-eligible request capacity is `R_A-1`.

| Profile | R_A | Delta_A | Horizon | Max requests | Guaranteed serial depth | Agent-access bytes | Total with frozen Gateway | Intended scope |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| P1 | 2 | 350 ms | 725 ms | 1 | 1 | 4,702,800 B | 5,681,759 B (5.419 MiB) | ordinary single-Agent sessions |
| P2 | 4 | 350 ms | 1425 ms | 3 | 2 | 9,405,600 B | 10,384,559 B (9.903 MiB) | default V14 functional corpus, including two-level nested retrieval |
| P3 | 12 | 350 ms | 4225 ms | 11 | 6 | 28,216,800 B | 29,195,759 B (27.843 MiB) | higher-capacity option including historical six-level descriptor-transition demand |

## Selection

P2 is selected. The current paper-aligned V14 functional corpus has J=1 or 2 (median 1.5, p95/max 2) and maximum retrieval causal depth 2. P2 provides three admitted requests and guaranteed serial retrieval depth 2, leaving one request of non-causal headroom without paying for the historical 100-slot candidate. P1 cannot guarantee the nested path. P3 is retained only as an explicit high-capacity public option; selecting it would reveal that profile choice and would raise normalized traffic to 29,195,759 bytes/session.

P2 still has a material cost: 9,405,600 Agent-access bytes and 10,384,559 total public bytes (9.903 MiB) per session. This is reported directly rather than compared to an arbitrary pass threshold. The redesign is accepted because the measured cryptographic cadence is sustainable, the selected profile covers the supported V14 workloads with explicit bounded capacity, and Agent-access traffic falls by 96.0% from the infeasible 100-slot projection. It is not evidence of timing indistinguishability.

Overflow is fail-closed as `PROFILE_AGENT_ACCESS_CAPACITY_EXCEEDED`; the schedule never extends.

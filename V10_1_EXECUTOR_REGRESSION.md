# V10.1 executor regression

Status: **PASS**

- Old V10A selected cases executed: **NO**
- Fixtures: synthetic non-holdout and reconstructed V9.1 development strata only
- Accepted canonical runner available: **YES**
- Exit code: `0`

## Captured test output

```text
..............                                                           [100%]
14 passed in 23.90s

```

Handoff and Agent-as-Tool are explicitly ineligible in the frozen adapter registry because V10.1 has no generic canonical bridge for those families. No per-case adapter was added.

## Repository-wide regression follow-up

The first repository-wide run produced one transient failure in the non-holdout OpenAI `READ_ONLY` fixture. The immutable Go runner recorded `RESULT_COMMITTED` and `READY_PUBLISHED`, but returned no client result after its first public round stalled for about 703 ms, longer than the 555 ms public session budget; the remaining rounds then ran as catch-up slots. This observation is preserved as a scheduling/load limitation of the accepted runner, not discarded or reclassified as a holdout outcome.

Without changing code, profile values, or fixtures:

- the exact affected non-holdout fixture passed **10/10** repeated executions;
- the second repository-wide run passed **235 tests**, with **2 environment skips** for Windows Application Control blocking the local Pacer executable;
- no old V10A or new V10.1 selected case was involved in either run.

The dedicated pre-freeze harness regression remains the selection gate. The transient demonstrates why final independent execution should run on a controlled host and treat session-budget exhaustion as an explicit infrastructure failure rather than silently retrying a selected case.

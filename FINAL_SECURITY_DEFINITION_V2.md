# Final security definition V2

## Parties

- Trusted: Privacy Kernel, its keys, private queues, authorization/provenance state, and commit gate.
- Honest-but-curious untrusted compute plane: cloud LLM, specialist agent workers, agent execution server, RPC host, and storage/transport observer.

## Public configuration and leakage

Public values include the leakage-class identifier, runtime/framework, `H`, `Delta`, `B`, epoch boundaries, final public effect type/outcome, and declared overflow/failure class. Within one public class, protocol-visible worker/RPC activation envelopes, count, ordering, serialized size, coarse release/arrival timing, burstiness, and commit slot are intended to be protected.

## Primitive-level target

For two queued message streams with the same public configuration and public outcome, a paced-cover channel should emit computationally indistinguishable fixed-size envelope schedules at the attacker-visible endpoints. Real and cover envelopes must be indistinguishable, and cover envelopes must not produce effects.

## Exclusions

Microarchitectural/cache side channels, GPU scheduling and telemetry, performance counters, global Internet traffic analysis, arbitrary human response time, and endpoint activity not routed through the paced-cover channel are outside scope.

## Status

`STRUCTURAL PROFILE ONLY`.

The implementation supports fixed count/order/size and no dummy effects. The timing clause is not supported: state-family attacks remain significant and deadline-slip distributions differ by state. The current one-direction five-slot epoch is a finite primitive test, not a proof for bidirectional persistent channels or full adaptive agent trajectories.

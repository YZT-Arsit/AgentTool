# V12 Duplex Private Completion-Wait Erratum

Status: frozen before the fifth functional requalification attempt.

The V4R3 Microsoft causal-depth identity produced all 100 public Registry
queries and responses, all 506 Relay cells, and zero Gateway response deadline
misses. A host scheduling stall made one private bridge-control response reach
the Python consumer 149.560 ms after enqueue. The private completion thread
used 110 ms (answer delay plus one nominal period) as a response-existence
timeout and therefore rejected a response that the public transcript had
already emitted correctly.

V4R4 changes only that private consumer wait: it uses the existing bounded
60-second session-liveness cap. Neither the open-loop query sender nor the
Registry response clock waits for this consumer. No public deadline, profile
field, size, count, identity, statistical method, or protected result changes.

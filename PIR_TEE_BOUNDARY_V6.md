# PIR / trusted-module boundary V6

The pinned official SimplePIR server holds fixed-width encrypted descriptor
rows. `O_registry` observes server-side query bytes, dimensions, answer bytes,
and work, but not the client index. The trusted module owns query randomness,
client hints/state, selected index, recovery, descriptor key, and plaintext.

SimplePIR provides selection privacy, not database confidentiality; row AEAD
provides the latter. PIR does not hide a later named activation. V6 therefore
passes only an opaque route handle into a common Gateway boundary.

`results_v6/pir_to_gateway_smoke/result.json` proves the real recovered row is
consumed by the V6 trusted module and produces a fixed 1,024-byte Gateway frame
without secret plaintext. Live Gateway process execution of that composition
was environment-blocked, so the boundary result is `PASS` through wire
construction and `PARTIAL` end to end.

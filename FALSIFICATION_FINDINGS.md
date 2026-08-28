# Falsification findings

1. **End-to-end target privacy is not validated.** The mock lookup exposes the
   index; the common executor only removes named activation after selection.
2. **Arbitrary framework behavior does not fit.** Dynamic instruction callbacks,
   prompt-encoded control, arbitrary Python predicates, and native parallel
   fan-out are unsupported. The claim must remain limited to declarative,
   ABI-conforming control.
3. **Secure transition evaluation is simulated.** The private fixed scan is
   small (estimated 4,744 gates), but no 2PC/garbled-circuit backend was
   integrated, so the cloud cannot yet safely evaluate a plaintext capsule.
4. **Tool privacy ends at the common adapter.** An independent observer of the
   ultimate external destination can recover Tool identity unless that path is
   separately protected.
5. **Timing privacy is not established.** Actual serialized lengths are fixed,
   but the cadence is nominal and the repository's earlier live timing work had
   residual leakage.
6. **The 100K timing is a direct-array feasibility bound.** It is not evidence
   that SimplePIR, Spiral, or another real single-server PIR meets latency,
   bandwidth, preprocessing, or memory requirements on this machine.
7. **Capsules currently fit because behavior is coarse.** Richer declarative
   policies or more than 30 rows require a larger public profile or multiple
   fixed pages, which may create a new public leakage class.

These are conditions on the method, not polish items.

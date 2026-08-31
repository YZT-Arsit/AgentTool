# V12 Timing Threat Model

This threat model was frozen before any timing-runtime modification.

The primary adversary is a passive metadata observer at one modeled application-channel boundary. The two primary observers are evaluated separately: the PIR Registry and the OHTTP Relay. Registry/Relay collusion is outside the frozen model; no joint view may be introduced after results are observed.

The passive observer may record all timestamps, sizes, and public connection/session/profile metadata available at its interface. It does not control the guest scheduler, hypervisor scheduler, CPU starvation, VM suspension, or the trusted timing component. Protection against an actively malicious scheduling host is out of scope.

The provider is a separate boundary. A provider necessarily learns that it was invoked and sees its own request. This phase does not claim provider-invocation hiding from that provider.

Registry timing is inside the claim because Agent-selection privacy would otherwise hide only the selected PIR index while exposing whether and when a real resolution occurred. Relay application-channel timing is also inside the claim. Packet-level timing, global Internet traffic analysis, malicious-hypervisor resistance, and hardware TEE validation remain open or untested.

The prior 10/20/25 ms strict-deadline failures remain `FAIL_NO_QUALIFYING_CANDIDATE`; this phase does not regrade them.

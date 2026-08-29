# Online canonical session V11.2

`CanonicalOnlineSession` owns exactly one Go runner process for the entire native framework run. The runner establishes one Client-to-Relay and one Relay-to-Gateway HTTP/2 connection before T0, prebuilds 111 NOOP requests, and runs the scheduler concurrently with response decapsulation and trusted result delivery.

The final development profile remains 111 rounds, 50 admission rounds, 1079-byte requests, 800-byte responses, 5 ms period, and 555 ms scheduled lifetime. A fixed 50-period public setup lead occurs before slot 1 so native framework startup does not consume the H50 admission window; it cannot be extended by private work. Completion does not terminate the public schedule early. Static-plan mode remains available only as frozen regression evidence.

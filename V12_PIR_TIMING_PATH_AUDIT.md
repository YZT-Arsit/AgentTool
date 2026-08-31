# V12 PIR Timing Path Audit

At base commit `ca6a79a92f3c6730f0909e015de1c6db722ac812`, each `CanonicalOnlineSession.submit()` synchronously calls `OnlineSimplePIRResolver.query()` only after a private action intent exists. That method immediately writes the real index to the interactive SimplePIR bridge. No fixed opportunity loop and no dummy PIR query exist.

SimplePIR hides the index value from the Registry, but the Registry-visible trace contains exactly one request for each real resolution. Consequently, query frequency and arrival time reveal the private resolution pattern. This is a genuine timing channel, not a scheduler artifact.

Registry timing is frozen inside the claim. The required repair is therefore a fixed 50-opportunity schedule using the same real SimplePIR protocol for real and dummy selections. A real request queues for the next opportunity; no secret-triggered query may bypass the schedule.

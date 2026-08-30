# V12.1 targeted B5 reliability audit

The repaired Linux runner completed the preregistered fresh DEV denominator exactly once: count 25 **100/100**, count 50 **100/100**, total **200/200**. No failed decisive identity was retried or replaced.

Every session emitted 356/356 rounds, had zero scheduler misses, matched every expected/submitted/PIR-recovered/accepted/admitted/provider/committed/available/framework-delivered operation-ID set, and ended COMPLETE with empty pending, unresolved, not-admitted, and waiter sets. Dummy-heavy operations, profile overflow, and silent committed-result loss were zero. Actual Relay sizes were 1079-byte requests and 800-byte responses for every round.

This closes the targeted B5 reliability endpoint on the frozen Linux development platform. It does not establish timing privacy and it does not override the later full-suite gate.

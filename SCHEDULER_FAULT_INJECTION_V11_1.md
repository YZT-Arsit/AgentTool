
# V11.1 scheduler fault injection

The non-holdout 75 ms delayed HTTP/2 stream case passed while later slot
streams continued to launch.  The scheduler-stall case passed only by producing
`SESSION_SCHEDULE_FAILURE`; it was not a functional pass and the expired slot
was not emitted as catch-up traffic.

Fault-injection checks: **2/2**.
Result: **PASS**.  These are liveness and
fail-closed tests, not timing-privacy evidence.

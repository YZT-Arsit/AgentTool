# Online admission policy V11.2

Admission is limited to public slots 1 through 50 and at most 50 accepted real operations. The public session never extends. A resolved action without a remaining eligible cutoff is rejected privately as `PROFILE_ADMISSION_CLOSED`; a 51st unique submission is `PROFILE_CAPACITY_EXCEEDED`.

At session end the runner separately reports admitted operations, delivered results, resolved-but-not-admitted IDs, unresolved IDs, pending operation IDs, and framework waiters. COMPLETE requires no pending accepted waiter and no silent committed-result loss.

The policy is safe but not sufficiently capacious for the full requested workload: under the final development configuration, 3/20 pre-freeze ten-action sessions reached `PROFILE_ADMISSION_CLOSED` before action ten. This is an explicit private capacity failure, not silent loss and not a public-session extension.

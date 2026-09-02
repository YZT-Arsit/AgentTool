# V12 Duplex P10 Candidate Eligibility

The immutable duplex functional evidence was audited candidate by candidate.
All 16 P10 records pass every required common-integrity and functional check;
therefore `P10_DUPLEX_FUNCTIONAL_ELIGIBILITY = PASS` with zero new sessions.

P10 and P20 were executed by the same frozen process under repository commit
`076bdbe18ffdd982462cd502b30f7b14a46eb520`, the same source/module/binary
manifest, and the same protected runtime. Their candidate-specific public
profiles differ only in predeclared public parameters. No P10-to-P20 runtime
change occurred.

P20 remains `FAIL_UNRESOLVED`: immutable identity
`DEV-DTVR-V4R5-P20-MS-CACHE_REUSE_30-007` returned 13 of 30 expected
operations, and its root cause is not established. That unresolved
candidate-specific observation does not retroactively invalidate the exact
P10 16/16 result in the absence of a mechanically established common defect.
P25 remains `NOT_TESTED`.

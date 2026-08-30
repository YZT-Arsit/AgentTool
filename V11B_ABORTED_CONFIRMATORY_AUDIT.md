# V11B Aborted Confirmatory Campaign Audit

V11B is permanently classified **STARTED / INCOMPLETE / NO RETRY**. Its holdout
was consumed, but it produced no confirmatory privacy verdict. The 157-record
append-only ledger contains 65 native `PASS` records and 92
`CANONICAL_FUNCTIONAL_FAIL` records. Unit 158 entered execution but no final
ledger record was committed.

The recurring canonical failure was `FileNotFoundError: online SimplePIR
requires Go and gcc`; the terminal failure was `OSError: [Errno 24] Too many
open files`. These are harness/runtime failures and are not counted as privacy
failures. No missing record, summary, completion anchor, or pair verdict has
been synthesized, and no selected unit has been rerun.

The separately frozen recursive result-tree manifest binds every existing byte
of the remote result tree. V11B may be cited only as an aborted harness run.

- `V11B_HOLDOUT_CONSUMED = YES`
- `V11B_RERUN_ALLOWED = NO`
- `V11B_CONFIRMATORY_RESULT_AVAILABLE = NO`

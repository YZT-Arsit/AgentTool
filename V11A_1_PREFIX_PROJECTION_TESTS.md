# V11A.1 prefix-projection tests

- Synthetic non-holdout unit tests: **3/3 PASS**.
- Reconnect fixture: prefixes 50 and 100 see one connection; prefix 200 sees two.
- A controlled public difference after round 150 is absent at prefix 100 and present at prefix 200.
- Every per-round and nested connection sequence has length `h` at [1, 10, 50, 100, 200, 300, 356].
- `prefix(356) == full projection`: **PASS**.
- Existing immutable V11.4 development traces: **12/12 pairs**, all seven corrected prefixes equal; no workload rerun.
- Selected V11A executions: **0**.

Test-output SHA-256: `941cc596699c6eb452740406a037c1ffd90644ce1594e8b1321095cf8cd0da52`.

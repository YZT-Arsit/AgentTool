# V12.3 Test Classification

Frozen before V12.3 execution from the immutable V12.2 302-node classification.

- `CURRENT_SYSTEM_EXECUTION_REACHABLE`: 116
- `HISTORICAL_EVIDENCE_AUDIT`: 176
- `PLATFORM_SPECIFIC_PORTABILITY`: 10

Exactly one semantic correction was made: the V11B0 prestart output-root guard is historical because V11B has permanently executed and its failed output root is intentionally retained. The historical test itself is unchanged.

All eleven `tests/test_v10_1_executor.py` nodes remain current-system execution-reachable. No other node changed class or reason.

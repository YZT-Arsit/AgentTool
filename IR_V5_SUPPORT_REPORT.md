# IR V5 support report

V5 adds a deployment verifier and confidential boundary; it does not relabel
the frozen corpus. Current executable support remains the bounded model/Tool
loop, logical handoff, private Agent call/return development path, basic scoped
state reference operations, declarative branch, and return.

`CALL_AGENT/RETURN_AGENT` retains its development evidence and private bounded
call stack. The fresh V3 holdout did not include Agent-as-Tool because available
official cases were already used in development, so confirmatory support is
still open. HITL/resume, bounded fork/join, general state lifecycle, arbitrary
callbacks, and unbounded control remain unsupported.

`IR_DESIGN_PARETO_V5.csv` records zero claimed corpus promotions. The next IR
extension should be selected by newly executable whole workflows per added
trusted LoC, not raw behavior count.

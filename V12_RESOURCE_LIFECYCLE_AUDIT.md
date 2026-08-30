# V12 resource lifecycle audit

The V11B descriptor exhaustion was caused by partial context entry. Provider
servers were entered before SimplePIR startup; when SimplePIR raised, Python did
not call `CanonicalOnlineSession.__exit__` because `__enter__` never returned.
Each failed selected canonical unit therefore retained provider sockets/threads.
Separately, successful `Popen` shutdown did not explicitly close every PIPE
object.

The generic repair now:

- constructs provider and PIR objects before entry and wraps all entry work in
  one exception cleanup path;
- closes stdin/stdout/stderr in `finally`, and waits after terminate/kill;
- closes partially entered PIR and provider resources in reverse order;
- snapshots PIR query evidence before clearing live references;
- contains no V11B/V12 case-ID branch and does not raise the FD limit.

Linux `/proc` instrumentation records self FD, socket and pipe counts, direct
children, zombies, and exact SimplePIR/canonical-runner executable identities.
The decisive 500-unit thresholds were frozen before its first unit. Earlier
development attempts that failed before, or were halted after discovering an
evidence-order defect, remain preserved.

The decisive Linux run completed **500/500** canonical units. `/proc` samples
at unit 0 and every tenth unit through 500 all reported 3 open FDs, zero open
sockets/pipes, zero live or zombie children, and zero orphan SimplePIR or
canonical-runner processes. The final-100 sample sequence is constant rather
than monotonically increasing. Five subsequent shape-equivalent rehearsals
each completed 158/158 ledgered units and 14/14 structural-pair verdicts.

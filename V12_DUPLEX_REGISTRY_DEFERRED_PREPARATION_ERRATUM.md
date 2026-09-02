# V12 Duplex Registry Deferred-Preparation Erratum

Status: frozen before the fourth functional requalification attempt.

The V4R2 causal-depth functional identity preserved all 506 Relay cells and
all 100 Registry queries, and the new Gateway response pipeline had zero
deadline misses. The first two real descriptor resolutions, however, reached
the bridge after their 5 ms PIR preparation cutoffs. The bridge correctly put
a prebuilt dummy query on each expired public opportunity, but the private
completion path incorrectly converted that cover substitution into permanent
failure of the waiting semantic operation.

V4R3 freezes a 20 ms public PIR commitment lead. More importantly, a real
resolution whose preparation misses an opportunity remains privately pending.
The expired opportunity emits its fixed-shape dummy, reports a fixed-size
private `PIR_DEFERRED` control result, and cannot be retroactively filled. The
same pending resolution can be selected only at a later public cutoff, and only
if its original enqueue timestamp predates that cutoff.

Q=100, the 60 ms public PIR period, 6000 ms epoch, 25 ms public origin lead,
fixed query/answer shape, 50 ms answer release delay, H, Delta, R, M, and the
Gateway response pipeline remain unchanged. No protected classifier or AUC is
involved.

# Named-activation lower-bound observation

Let `S` be the set of named Agent/Tool activations visible to the cloud. Suppose
correctness requires the real target `i` to be in `S` with probability at least
`1 - epsilon`. Full-domain target privacy requires the distributions of `S`
under targets `i` and `j` to be computationally indistinguishable.

The predicate “does named target `x` appear in `S`?” is efficiently computable
from the cloud view. If its probability were high when `x` is real and much
lower when another target is real, that predicate would distinguish the two
distributions. Hence, for every `x`, its inclusion probability under every
target must be approximately at least `1 - epsilon` (up to negligible privacy
slack). By linearity of expectation:

```text
E[|S|] = sum_x Pr[x in S] >= N(1 - epsilon - negligible).
```

Thus visible named cover sets with `k << N` cannot meet this full-domain goal;
repeated calls make their subset leakage worse. This is motivation for making
logical Agent identity private data behind one common executor, not a claim of
novel theory.

# V12 V4R7 duplex repair smoke protocol freeze

This development-only repair screen is frozen from `06bb4677fe51defb8823a1fcaf685856cda15845`. It uses the unchanged V4R7 P10 public profile (`H=4500 ms`, `B=200 ms`, `Delta=10 ms`, `M=50`, `R=521`, `Q=100`, response lag `30 ms`, response preparation lead `20 ms`).

Five physical task/framework coordinates produce seven application-operator comparisons. Each coordinate has 32 planned TRAIN and 32 planned EVAL matched blocks; the first 30 complete blocks in each partition by frozen priority are selected. The 640 identities execute once with no retry, replacement, identity search, or seed search.

Collection precedes all classifier fitting and statistical inspection. The V3.1 TRAIN-only four-model procedure is unchanged. A comparison triggers the development smoke failure only when its one-sided complete-block bootstrap `LCB95 > 0.65`. Absence of that condition can authorize a full development sentinel, but cannot establish timing privacy.

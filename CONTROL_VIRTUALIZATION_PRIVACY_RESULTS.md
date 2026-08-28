# Control-virtualization privacy results

Symbolic equality was checked before statistical inference. The host trace
contains one physical executor identity, four fixed slots, actual 1,024-byte
request/response frames, the common Tool boundary, and nominal public schedule.
It contains no logical Agent ID or named Agent endpoint.

| Design / boundary | Top-1 | Top-10 | Pairwise AUC | Result |
| --- | ---: | ---: | ---: | --- |
| B0 direct named execution | 1.000 | 1.000 | 1.000 | fails |
| B1 visible 8-cover, one call | 0.125 | 1.000 | n/a | fails full-domain privacy |
| B2 common executor only, N=1,000 | 0.001 | 0.010 | 0.500 | exact structural/size equality |
| B2 including mock lookup server | 1.000 | 1.000 | 1.000 | end-to-end privacy unvalidated |

For B1, the mean intersection candidate count was 8.00 after one call, 1.06
after two calls, and 1.00 after four and eight calls. Attacker top-1 probability
therefore rose from 0.125 to 0.970 after two calls and 1.000 after four calls,
versus full-domain chance 0.001.

The B2 structural result is exact, so a classifier would add no information.
It is not an end-to-end privacy result because the mock lookup reveals the
selected row. Timing and ultimate external Tool destination privacy are not
claimed.

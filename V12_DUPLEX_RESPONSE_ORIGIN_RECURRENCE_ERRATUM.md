# V12 Duplex Response-Origin Recurrence Erratum

Status: frozen before functional attempt 6. This is a runtime-development correction, not timing-privacy evidence.

V4R4 incorrectly used the 50 ms cold-start response allowance as the preparation lead for every slot. In the OpenAI causal-depth-50 functional unit, that consumed the causal admission horizon: 47 of 50 operations returned and the remaining three were resolved but not admitted, despite a complete 506-cell public transcript and zero response-release deadline misses.

V4R5 separates the public first-response origin from steady response preparation:

- `F_1 = max(E_1 + 50 ms, gateway_arrival_1 + 50 ms)`.
- For `i > 1`, `F_i = max(E_i + 20 ms, gateway_arrival_i + 20 ms, F_(i-1) + Delta)`.
- `G_1 = F_1 - 50 ms`; for `i > 1`, `G_i = F_i - 20 ms`.

The recurrence remains secret-independent. H, Delta, R, Q, sizes, the forward action clock, and statistical methodology do not change. The 20 ms steady lead exceeds three times the largest observed steady preparation duration from the prior development attempt (about 6.18 ms); this observation fixes no outcome-dependent privacy parameter and will be tested by a fresh, pre-frozen functional campaign.

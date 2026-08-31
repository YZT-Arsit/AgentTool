# V12 causal PIR capacity model

The old rule `Q=M=50` is **rejected**. A dummy opportunity consumed before a future causal arrival cannot later serve that arrival.

The capacity candidate uses a fixed public PIR epoch. The development candidates were frozen as epochs `{6000, 8000, 10000}` ms and periods `{60, 75, 100}` ms before live outcomes. The smallest integral candidate is `epoch=6000 ms`, `period=60 ms`, hence `Q=100`. This is a capacity-valid candidate construction, not the final timing profile.

The deterministic model uses `K=6`, 25 ms initial lead, 50 ms fail-closed query completion bound, and a 2589 ms latest new-descriptor arrival cutoff. It passes all K immediate, a first request at the supported boundary, causal generation after prior resolution/result, arrivals just after opportunities, pending bursts, and cache-hit/new-resolution mixtures. Maximum queue occupancy is 6 and worst modeled resolution delay is 409.999 ms.

No modeled trace adds an immediate real-only query, accelerates the period, extends the epoch, or omits a scheduled dummy.

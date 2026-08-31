# V12 MDCC dependency audit

The phase changed `v11_online/frameworks.py` and development/freeze harness files. No Go source, Go build input, SimplePIR source/binary, OHTTP/BHTTP implementation, timing profile, scheduler, public pacer, admission horizon, PIR period, PIR epoch, PIR initial lead, or Relay/Gateway binary changed.

Accordingly, the prior non-timing Go result remains valid at `70/70`. The two security-negative properties affected by the Python adapter change were frozen and rerun: duplicate operation-ID rejection before framework construction and rejection of a 51st real operation by the public system capacity. Both passed. The other 20 frozen non-timing security negatives retain unchanged executable dependencies, so the aggregate remains `22/22`.

The transitive runtime manifest was rebuilt because the Python adapter and live-capacity driver changed. Actual-host verification passed `696/696` runtime files, `10/10` Python module-file probes, and `2/2` frozen binaries.

The PIR candidate parameters were not changed: `K=6`, `PIR period=60 ms`, public epoch `6000 ms`, `Q=100`, initial lead `25 ms`, latest new-descriptor cutoff `2589 ms`, and action horizon `H=3000 ms`.

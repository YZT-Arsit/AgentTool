# V15B cryptographic cost decomposition

## Mechanical finding

The V15A 129.003 ms median complete access-slot time did **not** include a new
APSI process, SenderDB load, receiver process, SimplePIR process, database
preprocessing, or TCP/ZMQ connection setup per slot. `Harness.__init__` starts
each service once and `run_slot` reuses the same processes. Its excess cost
comes from serially executing two genuine per-slot operations: APSI followed
by SimplePIR.

V15B keeps the same real backends and overlaps those independent public stages.
Across 2,500 warm slots (500 for each frozen private mix), the complete
overlapped work was 58.673 ms p50, 68.727 ms p95, 93.058 ms p99, and
232.087 ms maximum. APSI was 54.194/65.071/74.182 ms at p50/p95/p99;
SimplePIR was 57.104/66.560/89.075 ms.

## Lifetime classification

| Component | Lifetime | Measured/audited treatment |
|---|---|---|
| APSI SenderDB construction | per store epoch | Prebuilt by the V14 database builder; never in a slot. |
| APSI SenderDB load and sender bind | per service/store epoch | One persistent sender. The harness used a conservative 1000.397 ms ready wait; the sender binary exposes no separate ready event, so DB-load time is not claimed independently. |
| APSI receiver process, parameter request, and ZMQ connection | per persistent receiver service | One receiver bridge process and one ZMQ channel. Python process creation took 5.348 ms; channel/parameter setup completes before slot traffic. |
| SimplePIR database load/preprocessing | per service/store epoch | One persistent interactive process; 77,988.142 ms from process start to `PIR_READY`. This is a substantial startup cost, but not a per-slot or per-session cost while the service remains warm. |
| Private FIFO and one-slot register initialization | per session | Local trusted bookkeeping; no cryptographic transcript. |
| APSI OPRF randomness and exchange | per slot | Fresh real APSI operation. |
| APSI query construction, server evaluation, result transfer/processing | per slot | Fresh real APSI operation. |
| PSI label decode | per slot | Trusted local processing. |
| SimplePIR query randomness, generation, answer, and recovery | per slot | Fresh real SimplePIR operation. All 2,501 measured query transcript hashes were unique. |
| Artifact decode | per provisioned result | Trusted processing after the downstream PIR stage; excluded from the cryptographic stage latency summary. |

## Cold and warm interpretation

The first measured slot after all services reported ready took 73.717 ms. This
is a first-query observation, not full cold deployment latency. Full cold
deployment additionally pays the store-epoch service initialization above,
dominated here by SimplePIR preprocessing. No query result, membership answer,
OPRF randomness, or PIR randomness is cached or reused.

Sources: `scripts/run_v15a_real_profile_feasibility.py`,
`scripts/run_v15b_pipeline_benchmark.py`, `V15B_PIPELINE_BENCHMARK.csv`, and
`V15B_PIPELINE_SUMMARY.json`.

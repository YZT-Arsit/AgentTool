# V6 performance report

`PERFORMANCE_RESULTS_V6.csv` separates measured values from models and missing
baselines. Provider/LLM execution is excluded from privacy overhead.

Key measured costs:

- 100K encrypted descriptor PIR: 52.240 ms mean online
  query+answer+recovery, 73,568 aggregate upload+download bytes for the reported
  run accounting, 75.3 MB client state, 34.4 s full preprocessing, 1.35 GB peak
  allocation;
- trusted 100K exact capability index: 2,388,890 encoded key/value payload bytes;
- AgentDescriptor and ActionCell width: 1,024 bytes each;
- project-owned TrustedActionModule: 406 code LoC; Gateway: 2,030 code LoC;
- dummy heavy operations: 0 in every completed V6 test/development run.

B1, B3, and B4 were not implemented as isolated offline baselines. B6 is only a
partial component composition because live opaque-Gateway continuation failed
the environment/functional gates. The unified-vs-hierarchical and cache tables
are measured-component models, not direct end-to-end latency distributions.

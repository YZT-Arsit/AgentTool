# Control-virtualization cost results

| N | Real heavy ops | Dummy heavy ops | Lookup ops | Control ops | Frames | Frame bytes | Server registry |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 1 | 0 | 1 | 4 | 4 | 8,192 | 1.024 MB |
| 10,000 | 1 | 0 | 1 | 4 | 4 | 8,192 | 10.24 MB |
| 100,000 | 1 | 0 | 1 | 4 | 4 | 8,192 | 102.4 MB |

The fixed-scan control step averaged about 0.59 us. At N=100,000, mock lookup
plus control averaged 1.08 us. A local 100,000-round SHA-256 loop used only as a
representative one-heavy-operation CPU proxy took 35.23 ms. It is not an LLM or
Tool latency measurement.

Wire accounting is 1,032 bytes for the mock lookup plus 8,192 bytes for four
request/response frame pairs. Real PIR communication, preprocessing state, and
client hints are absent and could dominate these figures. Cadence waits and live
timing costs were not measured in this structural stage.

# 100K private lookup results

No compatible real PIR dependency was installed. The official SimplePIR
reference requires Go and a C compiler; neither toolchain was present, and no
SealPIR/Spiral/Python PIR package was available. The measured backend is therefore
`MOCK_PRIVATE_LOOKUP_NON_CRYPTOGRAPHIC`; it exposes the index and validates only
registry construction and the lookup ABI. See the [SimplePIR reference
implementation](https://github.com/ahenzinger/simplepir) for the deferred real
backend candidate.

| N | Registry | Preprocess | Lookup mean / p95 | Response | Client memory |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 1.024 MB | 0.404 ms | 0.492 / 1.300 us | 1,024 B | 1,024 B |
| 10,000 | 10.24 MB | 4.099 ms | 0.365 / 0.600 us | 1,024 B | 1,024 B |
| 100,000 | 102.4 MB | 45.644 ms | 0.494 / 0.900 us | 1,024 B | 1,024 B |

All 100,000 rows were actually allocated, and the serialized header carries a
distinct logical ID for every row. These direct-array timings are **not PIR
performance** and provide **no target privacy**. Consequently condition C is
only an architectural scale pass, not a cryptographic scale pass. Sub-microsecond
single-operation measurements are timer/noise sensitive; raw data is retained.

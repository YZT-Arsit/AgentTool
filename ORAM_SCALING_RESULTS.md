# ORAM scaling results — OPTIONAL_PRIVATE_STATE_BACKEND (historical)

This result does not support Agent selection, dispatch, Tool invocation, or
named execution-identity privacy.

The existing Path-ORAM trace simulator was measured for 64 reads and three seeds. Payload cryptography and production networking remain abstracted.

| Records | Mean access | Physical bytes/access | Max stash | Trusted client bytes |
| ---: | ---: | ---: | ---: | ---: |
| 256 | 25.3 us | 36,864 | 0 | 1,056 |
| 1,024 | 40.8 us | 45,056 | 0 | 4,128 |
| 4,096 | 63.0 us | 53,248 | 2 | about 16.5 KiB |
| 16,384 | 82.0 us | 61,440 | 1 | about 64.1 KiB |

This is an implementation-cost study, not a new ORAM result.

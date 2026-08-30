# V12 performance summary

Thirty-attempt baseline/count cells complete: **YES** (30/30). FULL_STRICT successful-session Relay byte equality: **PASS** (146/150 successful attempts; 4 retained failures). Every successful strict session contains 356 requests of 1079 bytes and 356 responses of 800 bytes, for 668,924 action-transport bytes. PIR request/response bytes and combined total bytes are reported separately.

| Real operations | FULL_STRICT action-transport amplification vs direct logical bytes |
|---:|---:|
| 1 | 13116.16x |
| 5 | 2602.82x |
| 10 | 1173.55x |
| 25 | 457.54x |
| 50 | 222.60x |

The interrupted first performance campaign is retained. It stopped after a real `SESSION_SCHEDULE_FAILURE` in B5 count=25 repetition=3; that failed strict unit was not retried or replaced. A recovery campaign reran only B0-B3 because their metrics had existed solely in the terminated process, reconstructed every completed strict attempt from immutable evidence, and executed only strict identities that had never run. CPU/RSS are unavailable for reconstructed strict attempts and their measured-repetition counts are explicit in the CSV. The B2/B3 development helper uses the pinned RFC 9292/9458 code across a real loopback Cloud->Relay->Gateway exchange with exact Relay byte forwarding and one deterministic local provider invocation per real operation. The decisive binary was built offline with the repository's vendored ohttp-go dependency tree (`GOPROXY=off`); it contacts no external provider. An earlier module-mode build probe attempted the host's default Go proxy, timed out without obtaining the missing modules, and produced no binary or measurement; that failed environment probe is excluded. The CSV reports median, p95, mean, and population standard deviation for available latency, bytes, aggregate controller/child CPU, and process/campaign RSS high-water marks. B4/B5 action latency is computed from each operation's actual `ACTION_INTENT_SUBMITTED` to `FRAMEWORK_RESULT_DELIVERED` lifecycle timestamps. B0/B1 use the native framework-result boundary; B2/B3 use OHTTP client decapsulation. These are performance measurements, not timing-privacy claims.

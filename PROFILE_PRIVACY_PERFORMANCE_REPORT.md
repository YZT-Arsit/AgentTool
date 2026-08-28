# Profile privacy/performance report

`PROFILE_PRIVACY_PERFORMANCE_RESULTS.csv` evaluates declared operation counts
at enterprise hit rates 0.50, 0.80, and 0.95. It is a cost model, not a live TEE
benchmark.

- `STRICT` always pays one fixed private lookup and one common Gateway route,
  independent of hit/miss.
- `CONFIDENTIAL_ENTERPRISE` reveals the route and can omit the unused path.
- `ENTERPRISE_EFFICIENT` additionally exposes a configured internal Tool/action
  category and removes more cover work.

Higher internal hit rate therefore reduces external Gateway work in weaker
profiles, but the public route bit directly reveals a coarse activity class.
No cross-profile privacy comparison is valid. Live latency reduction remains
unmeasured until a hardware confidential runtime and real route adapters exist.

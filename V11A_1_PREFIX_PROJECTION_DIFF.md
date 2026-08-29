# V11A.1 prefix-projection difference

The accepted V11A full structural and size projections are unchanged. The old `structural_prefix()` truncated only endpoint, session, round, HTTP-version, and length sequences while retaining full-session cryptographic/configuration sequences and connection metadata.

The corrected function truncates all 15 per-round sequences, truncates both nested connection-reuse sequences, recomputes each prefix-local connection count from aliases visible by that horizon, preserves only public session/profile scalars, and sets `round_count = h`. `prefix(356)` is byte-for-value equal to the full structural projection. No timestamp is added.

No selected manifest, seed, execution order, candidate universe, V11.4 runtime component, canonical full projection, or size projection changed.

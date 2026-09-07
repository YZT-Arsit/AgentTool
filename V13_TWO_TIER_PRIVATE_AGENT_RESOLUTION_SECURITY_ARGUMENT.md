# V13 Two-tier Private Agent Resolution Security Argument

This is an internal engineering argument, not manuscript text.

Let `C_t` be the planner-selected candidate set, `E` the enterprise's
deployed-Agent set, `I_t = C_t intersect E`, and `b_t = 1[I_t is nonempty]`.

The fixed structural contract emits one public PSI slot and one public PIR
slot for every Agent-resolution opportunity. `C_t` is padded to K=8, and the
Enterprise Agent Directory is assigned the padded E=1024 public bucket. On an
enterprise-local hit the PIR slot uses the reserved padding row; on a library
fallback the PIR slot uses the selected real library row. Both destinations
are handed to the same trusted Gateway interface.

Subject to a future vetted PSI backend's privacy definition, existing
SimplePIR query privacy, trusted-runtime secrecy, and enforcement of the fixed
slot/size profile, the public structural transcript is independent of `b_t`.
It therefore does not disclose candidate IDs, enterprise inventory IDs, the
intersection, or the enterprise-hit/library-fallback branch beyond the public
K=8 and E=1024 profile parameters.

The present implementation does **not** instantiate cryptographic PSI. Its
mock backend computes raw set intersection for deterministic functional tests
and is not privacy evidence. No application-level timing indistinguishability
is claimed. Structural privacy is the intended positive guarantee after a
vetted PSI backend is integrated; realized timing remains a residual side
channel under the existing paper boundary.

# V12 V4R7 Provider Completion Bound Coupling Audit

Status: `ROOT_CAUSE = PROVIDER_COMPLETION_BOUND_TOO_TIGHT_FOR_DEPLOYMENT`.

The preserved V4R6 evidence shows provider logical work completing in 364006 ns while the trusted Gateway did not finish the provider HTTP exchange until 50856110 ns. The semantic completion boundary is therefore the trusted Gateway receiving and reading the valid provider response, not the shorter handler logical-work interval.

Mechanical source audit confirms that `ProviderCompletionBoundMS` controls all four required quantities:

1. `canonicalv9.newEngine` configures the trusted Gateway `http.Client.Timeout` from it.
2. `canonicalv9.engine.callProvider` records `ProviderDiagnostic.ContextDeadlineNS` from the same value.
3. `TimingIndistinguishabilityProfile.completion_rounds` is `ceil(B / Delta)`.
4. `TimingIndistinguishabilityProfile.total_rounds` is `ceil(H / Delta) + ceil(B / Delta) + M + T`.

The current error path separately diagnoses a context deadline but returns generic `StatusError`; V4R7 must map a genuine end-to-end completion deadline to `StatusTimeout` while retaining generic `StatusError` for transport and explicit provider errors.

The candidate set, measurement-only timeout, 10,000 unprotected attempts, percentile rule, and mechanical selection rule are frozen in `V12_V4R7_PROVIDER_BOUND_SELECTION_FREEZE.json` before measurement. The measurement timeout is not a candidate system configuration.

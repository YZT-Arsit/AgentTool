# Claim Audit

## Supported

- **Per-store ORAM does not hide cross-store mediation structure.** Supported in
  the Stage-3 reference mediator and GAAP-derived modular deployment.
- **Canonical modular mediation hides the evaluated cross-store structure.**
  Supported for every positive synthetic/source-derived workload tested.
- **Unified ORAM is an alternative mitigation.** Supported; it removes store
  identity and reaches chance on equal-work structural tasks.
- **Host-observable cross-store mediation structure can leak private execution
  state in modular privacy-preserving runtimes even when each store hides logical
  record addresses.** Supported with the deployment assumption made explicit.

## Conditionally supported

- **Canonical modular mediation is cheaper than unified ORAM.** Configuration-
  dependent. It was cheaper in Stage 3 and cheaper than unified-plus-padding for
  GAAP-derived. Unpadded unified GAAP transfers 312 blocks versus canonical's
  368, so no universal advantage exists.
- **The leakage occurs in real agent-security architectures.** Only in the
  carefully qualified sense that GAAP documents the required logical state and
  semantics. The experiment evaluates an added modular ORAM deployment, not the
  GAAP implementation.
- **ORAM is insufficient for mediation-trace privacy.** Only for independently
  address-oblivious, host-distinguishable per-store ORAMs. A unified ORAM defeats
  the demonstrated cross-store channel.

## Unsupported / prohibited

- **“ORAM is insufficient for agent privacy.”** Too broad and contradicted by
  unified-ORAM results.
- **“ORAM is insufficient for mediation-trace privacy.”** Prohibited without the
  per-store/modular qualifier.
- **“The leakage occurs in all agent architectures.”** Contradicted by the
  PAuth-derived negative result.
- **“Canonical modular mediation is always cheaper than unified ORAM.”** False in
  the GAAP-derived unpadded comparison.
- **“We reproduce GAAP/PAuth.”** False; these are architecture-derived local
  abstractions.
- **“We are the first to identify this leakage.”** No novelty review establishes
  this and the experiments cannot support priority.
- Claims of production ORAM security, real-world prevalence, network-traffic
  privacy, credential protection, or deployed-system effect size.

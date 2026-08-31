# V12 PIR resolution semantics

A real Registry PIR resolution is required for the first activation of an authenticated Agent descriptor in one catalog epoch, a change/handoff to a different Agent, an Agent-as-Tool target selection not already cached, or descriptor epoch/version invalidation. It is not semantically required for each Tool action while the same authenticated descriptor remains active and unchanged.

The trusted resolver now caches by `(catalog_epoch, agent_id)` inside one canonical online session. Cache hits remain private. They do not remove public Registry cover traffic: the fixed schedule performs a dummy query through the same SimplePIR protocol whenever no new real resolution is pending.

The complete current selected-runtime descriptor identity set is `{10, 11, 12, 13, 20, 21}`: Tool Agent, three effect-specific Agent services, trusted-module-local Agent, and workflow/composition Agent. Therefore the public real-resolution bound is `K=6`; this is not inferred from action capacity `M=50` or from a successful run.

Future actions, operation IDs, and Agent transitions remain online. No future sequence is supplied before T0.

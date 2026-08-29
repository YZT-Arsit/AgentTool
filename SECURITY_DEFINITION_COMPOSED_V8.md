# Optional Composed Registry + Relay Definition — V8

This optional game considers collusion between the SimplePIR registry observer and the OHTTP Relay observer. The secret combines selected Agent row/ID with inner action metadata. The composed public view is the union of the two documents' allowed leakage.

The intended argument requires both:

1. SimplePIR query privacy with trusted client state and fresh randomness; and
2. RFC 9458 confidentiality plus the fixed public transcript/size profile.

SimplePIR is not required inside the Relay-only game, and OHTTP is not credited for registry-index privacy. Composition is **OPEN** in V8 because the RFC 9458/RFC 9292 component is blocked. No end-to-end theorem or empirical holdout is claimed.


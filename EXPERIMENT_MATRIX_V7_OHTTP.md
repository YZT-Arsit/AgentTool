# Experiment Matrix V7-OHTTP

| Gate | Required evidence | Current result | Can support canonical claim? |
|---|---|---|---|
| RFC library provenance | pinned version/commit/hash/license | absent offline | No |
| RFC 9458/9292 conformance | Appendix A and known-length round trip | NOT_TESTED | No |
| Agent/Tool route separation | authorization and route unit tests | PASS | Yes, semantic subclaim |
| Relay opacity | exact RFC OHTTP bytes unchanged; no private log fields | contract PASS, RFC bytes absent | Partial only |
| 1/10/50/100 functional gate | actual OHTTP path, N/N delivery | NOT_RUN | No |
| Out-of-order result reliability | queue/journal/admission | 161/161 pre-OHTTP | Reliability only |
| Strict structural equality | actual OHTTP Relay traces | OPEN | No |
| Strict size equality | final Encapsulated Request/Response | OPEN | No |
| Long horizon | actual OHTTP exchanges | OPEN | No |
| Timing | observer-boundary confirmation | NOT_TESTED | No |
| Packet timing | lower-layer enforcement | OPEN | No |

No classifier is appropriate before functional and symbolic OHTTP equality
gates pass.


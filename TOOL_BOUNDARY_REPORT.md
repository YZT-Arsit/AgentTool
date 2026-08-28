# Tool Boundary Report

## Implemented boundary

```text
AgentControlExecutor
    -> fixed 1,024-byte AEAD envelope
    -> CommonToolExecutor
        -> LOCAL: temporary document adapter
        -> REMOTE: common egress relay -> controlled HTTP service
        -> CLOUD: compute inside the common Tool service
```

The direct baseline exposes `local-filesystem`, a distinct remote port, or `cloud-compute-process`. The protected
client always addresses `CommonToolExecutor`, with one equal-size request and response. AES-GCM uses a fresh nonce;
the ciphertext is not a stable Tool pseudonym.

`LOCAL` creates, reads, and modifies only a temporary synthetic document. `REMOTE` calls a controlled loopback HTTP
service through a separate common egress relay. `CLOUD` performs real hash computation inside the common Tool
service, not a named Tool-specific worker. All services are local and non-destructive.

## Closure status

| Property | Status | Boundary |
|---|---|---|
| Local Tool identity, structural/size | PASS | cloud sees common client/action endpoint |
| Remote destination, structural/size | PASS WITH ASSUMPTION | common egress is the cloud-visible boundary |
| Cloud-local Tool identity, structural/size | PASS | no named class-specific service activation |
| Multi-round Tool structural/size | PASS | fixed endpoint/count/1,024-byte envelopes |
| Tool timing | OPEN | not shaped |
| Tool resource trace | OPEN | common service resource behavior not shaped |

The remote result requires the common egress/tunnel endpoint to lie at the declared cloud boundary. An observer that
also watches traffic after the trusted egress can see the actual remote destination; that stronger destination
observer is not closed by this prototype. This assumption must be explicit in any later system claim.

## Multi-round falsification

Five 100-round profiles were executed for ten episodes each. Structural and size attacks are symbolically equal, but
timing exposes Tool behavior:

- Tool-class top-1: 0.714 logistic regression and 0.770 random forest (chance 0.333).
- Repeated-target timing AUC: 0.657 / 0.831 (both permutation p=0.0476).
- Frequency timing AUC: 1.000 / 0.989 (p=0.0476).
- Rare-Tool timing AUC: 1.000 / 1.000 (RF p=0.0476).
- Transition timing AUC: 1.000 / 1.000 (p=0.0476).

This is a decisive falsification of live Tool timing privacy, not a reason to remove timing features.

Every Tool sequence entry is a real requested Tool operation. No cover slot dispatches a concrete Tool and
`dummy_heavy_ops` is zero. Host and private logs are separate under `results_crypto_closure/tool_action/`.

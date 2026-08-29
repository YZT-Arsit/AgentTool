# V7-OHTTP Threat Model

## Protected information

Against the honest-but-curious enterprise Cloud Relay, the intended canonical
path protects Agent ID/name, Tool/provider name, action kind, route handle,
operation ID, arguments, results, and private authorization metadata.

## Public Relay view

The Relay may observe client/network identity, Relay and Gateway endpoints,
connection identity/reuse, public profile, request/response Content-Type and
fixed Content-Length, slot count/order, send/receive timing, and public
lifetime. It forwards the trusted-generated OHTTP body unchanged.

## Trusted views

- The OHTTP Gateway sees the inner action, private route handle, selected
  provider, and result.
- A provider sees its own invocation.
- The SimplePIR server sees the PIR transcript under the separately frozen
  threat model.

## Exclusions

RFC 9458 does not provide traffic-analysis resistance. Fine-grained timing,
packet-level timing, global traffic analysis, denial of service,
microarchitectural leakage, compromised Gateway/TEE code, provider-side
observation, and hardware TEE attestation are not closed here.

The current executable backend is not RFC 9458. Consequently the intended
Relay confidentiality property remains unvalidated in this environment.


# Current Security Definition V7-OHTTP

For executions in one public profile with equal allowed leakage

```text
L(tau0) = L(tau1) =
  (Relay endpoint, Gateway endpoint, public profile,
   connection policy, slot count/order/lifetime,
   fixed request length, fixed response length,
   allowed timing transcript)
```

the intended strict Relay view should be computationally indistinguishable
with respect to Agent identity, action kind, Tool/provider identity, route
handle, operation ID, arguments, results, and authorization state.

This definition relies on:

1. official SimplePIR query-index privacy under its stated assumptions;
2. authenticated Agent descriptors and trusted route-map correctness;
3. a conformant RFC 9458 implementation and authenticated Gateway key config;
4. equal final encapsulated lengths after RFC 9292 padding and HPKE overhead;
5. exact opaque Relay forwarding with no private headers/log fields;
6. the fixed public transcript and reliable queue/journal semantics; and
7. a trusted Gateway and trusted module/future TEE.

The current checkout does not satisfy assumption 3 and has not tested 4 on real
OHTTP bytes. Thus the definition is a target, not a demonstrated theorem.
Timing remains allowed leakage/unclosed; packet-level and global traffic
analysis are excluded. The Gateway and provider views are not required to hide
their own plaintext/invocation in the base model.


# Private routing report

The implemented V5 resolver was exercised with a TEE-resident synthetic
enterprise catalog. This makes PSI unnecessary. No audited PSI/OPRF package is
available offline; the outsourced-membership reference backend is explicitly
non-cryptographic.

For `STRICT`, internal and external resolutions have exactly equal public
projections:

```text
FIXED_PRIVATE_LOOKUP -> FIXED_COMMON_GATEWAY_SLOT -> CommonActionGatewayV2
```

The internal case uses the real index; the external case uses a reserved dummy
lookup and keeps its discovery handle private. For `CONFIDENTIAL_ENTERPRISE`
and `ENTERPRISE_EFFICIENT`, `ENTERPRISE` versus `EXTERNAL` is deliberately
visible. Unit tests also verify the public V5 trace omits capability and index.

This is symbolic and functional evidence using a local capsule lookup, not live
hardware-TEE or new PIR privacy evidence. The existing official SimplePIR result
is a separately preserved building-block result.

# V6 resource-observer audit

| Feature | Visibility domain | Used in a V6 attack? | Status |
|---|---|---:|---|
| PIR server CPU/RSS/query dimensions | `O_registry` | implementation audit only | visible, permitted scheme cost |
| cloud TCP endpoint/cells | `O_cloud_network` | planned structural/size view | partial live |
| trusted-module heap/CPU | `O_cloud_host` without hardware TEE | no | potentially visible |
| Gateway Worker/Pacer resource use | `O_gateway` | no | trusted external domain |
| provider CPU/GPU | `O_provider` | no | provider-only, not attributed to cloud observer |
| cloud-local Tool process | `O_cloud_host` | no classifier needed | directly identifies Tool class |

V6 does not move provider telemetry into an observer that cannot see it. It also
does not pretend fixed cells hide host process activity. `RESOURCE_PRIVACY =
OPEN`. STRICT against a malicious host requires a real confidential-compute
backend and appropriate placement/common-service boundary; no resource padding
was added merely to manufacture a PASS.

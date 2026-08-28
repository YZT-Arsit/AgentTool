# V5 Privacy Profiles

Profiles are separate leakage contracts. V5 makes no cross-profile
indistinguishability claim.

| Property | STRICT | CONFIDENTIAL_ENTERPRISE | ENTERPRISE_EFFICIENT |
| --- | --- | --- | --- |
| payload/plaintext | hidden | hidden | hidden |
| logical Agent/control | hidden | hidden | hidden |
| enterprise vs external route | hidden | public | public |
| handoff identity | hidden within public profile | hidden | hidden unless declared adapter leaks it |
| action type | hidden within fixed transcript | may be visible at endpoint | public/coarse |
| Tool identity | hidden only via TEE/common broker/Gateway | private only inside confidential boundary/broker | configured category may be public |
| external destination from Agent Cloud | hidden by common Gateway | not guaranteed | not guaranteed |
| cost | highest | medium | lowest |

## STRICT

Public leakage is limited to the chosen profile, public horizon, fixed frame
bucket, public outcome class, and agreed session policy. Internal hits and
external misses use one outer destination and equal public schedule. The miss
uses a cover PIR row; the internal route still uses the common Gateway slot.
No dummy heavy operation is permitted.

## CONFIDENTIAL_ENTERPRISE

Payload, logical Agent identity, capsule, and private control remain inside the
TEE. The `ENTERPRISE`/`EXTERNAL` route bit is public. Internal Tool identity is
protected only when the Tool is `TEE_LOCAL` or behind an equivalent
confidential/common broker. This profile does not promise action-type or
destination privacy for visibly distinct endpoints.

## ENTERPRISE_EFFICIENT

Payload and private Agent selection remain protected, but route class, action
class, and a configured internal Tool category may be public. Every disclosed
category must be named in configuration; omission is an error. The performance
benefit is avoidance of cover PIR/Gateway slots for the public route. It must be
reported with the coarse-activity leakage it creates.

## Public profile selection

`SHORT`, `STANDARD`, or `LONG` is selected before private execution from public
SLA/user choice/enterprise policy/experiment configuration. Selection may not
depend on the private Agent, route, or trajectory. Equal-profile executions
must have exact destination, slot count/order, request/response size, and public
session lifetime. Timing remains open until a reference-platform observer-
boundary experiment succeeds.

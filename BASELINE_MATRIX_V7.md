# Frozen Baseline Matrix V7

Status: **FROZEN BEFORE V7 CONFIRMATORY PRIVACY EXECUTION**

All baselines assume authenticated content confidentiality. Plaintext is not a
primary comparison.

| ID | Baseline | Selection | Action path | Public normalization | Intended observation |
|---|---|---|---|---|---|
| B0 | DIRECT_PROTECTED | ordinary/private out of scope | destination-specific protected/TLS action | none | endpoint and natural trajectory visible |
| B1 | PIR_ONLY | official SimplePIR descriptor lookup | direct concrete destination | none after lookup | descriptor index hidden from registry; endpoint exposed |
| B2 | COMMON_GATEWAY | same as B0 | one trusted Gateway destination | natural sizes/count/order/lifetime | destination hidden, remaining metadata exposed |
| B3 | GATEWAY_FIXED_SIZE | same as B0 | common Gateway | fixed application cell width | destination/size hidden; count/order/lifetime exposed |
| B4 | GATEWAY_FIXED_TRANSCRIPT | same as B0 | common Gateway | fixed width/count/order/public lifetime | structural/size target; fine timing unclaimed |
| B5 | V7_STRICT | unified encrypted AgentDescriptor SimplePIR registry | TrustedActionModule and CommonActionGateway V7 closure path | fixed action transcript | strict equal-profile structural/size target |
| B6 | V7_ENTERPRISE_EFFICIENT | trusted internal-first, external lookup on miss | declared cloud-local shortcut or Gateway | configured public profile | route/tool class deliberately public |

`B_FULL_DOWNLOAD` is excluded from the frozen primary matrix: it is an obvious
privacy upper-bound cost reference and is not necessary to interpret V7.

The matrix does not claim timing, packet-level, resource, hardware-attestation,
or rollback closure.

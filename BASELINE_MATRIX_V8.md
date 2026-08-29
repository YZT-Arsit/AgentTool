# Baseline Matrix — V8

No final baseline performance run was started because the canonical OHTTP path is blocked.

| ID | Name | Meaning | V8 status |
|---|---|---|---|
| B0 | DIRECT_PROTECTED_ACTION | Orthogonal protected payload plus destination-specific protected/TLS transport | Defined; not rerun |
| B1 | PIR_PLUS_DIRECT_ACTION | Private Agent lookup followed by destination-specific action | Defined; V8 PIR component measured only |
| B2 | OHTTP_UNSHAPED | RFC OHTTP through Relay without fixed transcript shaping | BLOCKED |
| B3 | OHTTP_PADDED | OHTTP with fixed final encapsulated sizes | BLOCKED |
| B4 | OHTTP_FIXED_TRANSCRIPT | B3 with fixed public rounds/lifetime | BLOCKED |
| B5 | STRICT | Canonical SimplePIR + trusted module + OHTTP + strict placement/profile | BLOCKED |
| B6 | ENTERPRISE_EFFICIENT | Hierarchical/deployment-efficient profile with declared route-class leakage | BLOCKED |

B0 does not imply that TLS alone protects upstream payload/host exposure. Historical custom AES-GCM framing remains `LEGACY_DEV_TRANSPORT`, not B2–B6 evidence.


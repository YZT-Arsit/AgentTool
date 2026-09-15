# Final claim matrix

| Claim | Classification | Exact evidence |
|---|---|---|
| same-Agent unlinkability | **PARTIALLY_SUPPORTED** | SAME_AGENT_WITHIN_SESSION / ALL_ALLOWED: 0.5139103887168902 |
| cross-session unlinkability | **PARTIALLY_SUPPORTED** | CROSS_SESSION_SAME_SLOT: 0.46792132369055445; CROSS_SESSION_CROSS_SLOT: 0.5209995088824537 |
| access ordering privacy | **PARTIALLY_SUPPORTED** | FOUR_CLASS_ORDERING_RECURRENCE / ALL_ALLOWED: 0.25245901639344265 |
| recurrence privacy | **PARTIALLY_SUPPORTED** | RECURRENCE_AAA_VS_ABC / ALL_ALLOWED: 0.478491512345679 |
| rare-Agent privacy | **PARTIALLY_SUPPORTED** | RARE_INSERTION_AAA_VS_AAB / ALL_ALLOWED: 0.5583847736625515 |
| return-pattern privacy | **NOT_ESTABLISHED** | RETURN_PATTERN_ABA_VS_ABC / ALL_ALLOWED: 0.3725694444444444 |
| deployed/unprovisioned/idle structural privacy | **ESTABLISHED** | PROVISIONED_UNPROVISIONED_IDLE / STRUCTURAL: 0.3333333333333333 |
| execution-trajectory structural privacy | **PARTIALLY_SUPPORTED** | FOUR_CLASS_EXECUTION_TRAJECTORY / FINAL_OAE_STRUCTURAL_COMPOSITION: 0.2125 |
| Agent-access realized timing privacy | **NOT_ESTABLISHED** | PROVISIONED_UNPROVISIONED_IDLE / TIMING: 0.6633333333333333 |
| Gateway realized timing privacy | **NOT_ESTABLISHED** | TOOL_VS_AGENT_AS_TOOL / FINAL_OAE_RELAY_TIMING: 0.645 |
| utility | **ESTABLISHED** | 240/240 |
| 100K scale | **ESTABLISHED** | schema-valid artifacts |
| bounded liveness | **ESTABLISHED** | maximum 3 admitted requests/profile |
| zero dummy-heavy compute | **ESTABLISHED** | measured utility campaign |

`PARTIALLY_SUPPORTED` for access attacks records that APSI wire content is used only for sessions whose three logical accesses have exact captured byte counts, while the SimplePIR adapter retained the actual query digest plus public sizes/timing but not the raw answer payload.
The trajectory result is an exact component composition, not a fresh integrated 800-session campaign.
Realized timing is excluded from every structural claim and remains **NOT_ESTABLISHED**.

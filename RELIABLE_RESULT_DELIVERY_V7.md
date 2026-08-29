# Reliable Result Delivery V7

The transport-independent V7 queue/journal/admission substrate delivered
161/161 admitted operations over the preserved 1/10/50/100-operation Linux
functional runs. There were no missing or unexpected results, duplicate
framework deliveries, terminal overflows, or dummy provider operations. Each
intended local effect occurred once under its declared idempotent test contract.

The durable queue supports out-of-order completion and can select an eligible
result even when an earlier queue entry belongs to a future session. Restart
tests cover reservation replay, committed-result recovery, effect-semantic
decisions, and trusted duplicate suppression. NON_IDEMPOTENT_EFFECT after an
ambiguous provider start produces an explicit unknown outcome rather than an
exactly-once claim.

These measurements used `LEGACY_DEV_TRANSPORT` before the OHTTP amendment. The
queue, journal, and admission logic are retained, but no RFC 9458 end-to-end
functional run occurred. Thus `RESULT_DELIVERY = 161/161` describes the
reliability substrate, not OHTTP protocol closure.


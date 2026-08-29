# Recovery Wiring Audit — V8

Status: `RECOVERY_LIVE_WIRING = PARTIAL`

| Component/property | Evidence state | Exact live path or limitation |
|---|---|---|
| Historical `OperationJournal` effect recovery | LEGACY_ONLY / LIVE_E2E in legacy worker | `cmd/gateway-worker` and `cmd/gateway-worker-v7` call root `RunWorker`; `worker.go` opens `OperationJournal`. It is not the canonical OHTTP path. |
| V7 `EffectRecoveryJournal` | UNIT_ONLY | Referenced by V7 recovery tests; no production command imports or opens it. |
| V7 `DurableReadyQueue` | LIVE_E2E in legacy V7 pacer | `v7/pacer.go` opens it and calls `ReserveEligible` and `MarkDelivered`. These calls persist JSON/files near the release path. |
| V8 trusted `DeliveryLedger` | UNIT_ONLY | Durable Python state machine; tests pass. It is not wired to a canonical OHTTP client because RFC 9458 is blocked. |
| V8 in-memory delivery handoff | UNIT_ONLY / COMPILE-ONLY | `v8.MemoryDeliveryQueue` and immutable `PreparedSlot`; Go compile and vet pass, runtime tests blocked by Application Control. |
| Canonical BHTTP/OHTTP recovery context | NOT_WIRED | No audited local RFC implementation exists. |

The intended canonical ordering is effect/result durable commit, bounded in-memory publication, pre-deadline slot preparation, minimal send, asynchronous delivered acknowledgement, and trusted-side replay suppression. Its pieces exist, but the missing RFC path and unwired production command prevent an end-to-end recovery PASS.


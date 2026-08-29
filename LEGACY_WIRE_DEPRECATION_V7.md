# Legacy Wire Deprecation V7

## Quarantined components

- `action_privacy_v6.models.ActionCellV6`
- `action_privacy_v6.trusted_module.LocalTrustedBackend.make_action_cell`
- `common_action_gateway_v2/protocol.go` custom AES-GCM frame codec
- `gateway_v7/runner.py` pre-encrypted custom-frame runner
- `common_action_gateway_v2/v7/pacer.go` custom-frame frontend

They are retained to preserve frozen V6 and pre-OHTTP V7 reliability evidence.
They are classified as `LEGACY_DEV_TRANSPORT`, not RFC 9458, BHTTP, HPKE, or a
canonical V7 security baseline.

## Canonical guard

`common_action_gateway_v2/v7ohttp` defines the new transport contracts. Its
legacy marker does not implement the canonical client/Gateway interfaces, and
`RequireCanonical` rejects every backend that is not both RFC-9458-capable and
status `PASS`. The Python marker similarly fails closed.

No prior artifact was deleted or rewritten. `V7_PRE_OHTTP_FREEZE_MANIFEST.json`
separates the earlier result set from any future OHTTP run.


# V12 current non-timing test classification

The classification is based only on the frozen selected-runtime call graph and support-component dependencies. Previous PASS/FAIL/SKIP outcomes are not inputs.

- Current gate: V12 driver/cleanup tests, provider diagnostics, native `v11_online` routing, current orchestrator/projection tests, descriptor/authorization/DeliveryLedger tests, and OHTTP/BHTTP architecture tests.
- Legacy compatibility: all Agent-IR V2 and V10.1 executor tests.
- Historical evidence only: the four result-tree `test_crypto_closure` nodes and five frozen V2/V4 artifact nodes.
- Platform-specific historical: the Stage-9 Windows `Scripts/python.exe` approval-path node.
- Stage-10: one source-compatibility node and eight historical experiment nodes; none is selected-runtime executable correctness.
- Timing-dependent: all `test_v12_final_runtime.py` nodes and the two canonical public-view V12-RC routing parameterizations.

The nine historical artifacts are not regenerated or copied into the Linux workspace. Their integrity is audited separately against the authoritative repository copy.

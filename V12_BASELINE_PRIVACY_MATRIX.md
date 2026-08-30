# V12 baseline privacy matrix

Development-only exact metadata-projection comparisons; timestamps are excluded.

| Baseline | Equal dimensions / 14 |
|---|---:|
| B0_DIRECT_NATIVE | 1/14 |
| B1_PIR_PLUS_DIRECT_ACTION | 2/14 |
| B2_PIR_PLUS_OHTTP_UNSHAPED | 11/14 |
| B3_PIR_PLUS_OHTTP_PADDED | 13/14 |
| B4_PIR_PLUS_FIXED_TRANSCRIPT_EXTERNAL | 13/14 |
| B5_FULL_STRICT | 14/14 |

B0/B1 expose direct action metadata. B2 closes destination/content but leaves unshaped count/size. B3 adds fixed size. B4 adds a fixed external transcript but does not close internal/external placement. B5 adds the common STRICT cover path and is equal in all 14 modeled structural/size dimensions. B2/B3 use the pinned RFC 9292/9458 implementation across a real loopback Cloud->Relay->Gateway exchange with exact Relay forwarding and a deterministic local provider emulator, built offline from the repository's vendored dependencies; no external provider is contacted. The first development baseline directory is retained but excluded because its B0/B1 response-size field was a placeholder; this matrix is generated only from the separately named one-shot corrected run with actual native result bytes. These are not timing-privacy results.

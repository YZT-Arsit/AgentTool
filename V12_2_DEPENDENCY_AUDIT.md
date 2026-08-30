# V12.2 executable-dependency audit

The V12.1 repair changed `common_action_gateway_v2/canonicalv9`, the V7 effect-recovery/ready-queue durable path, and V11.3 development diagnostics. It did not change the native B0 path, SimplePIR protocol or bridge, BHTTP/OHTTP codec, Relay/Gateway endpoint protocol, corpus classifier, or the B2/B3 local benchmark executable.

| Evidence | Dependency disposition | V12.2 action |
|---|---|---|
| B0 direct native | no changed executable dependency | preserve historical 1/14 |
| B1 PIR + direct action | no changed SimplePIR/native dependency | preserve historical 2/14 |
| B2 PIR + unshaped OHTTP | no changed benchmark/PIR/OHTTP dependency | preserve historical 11/14 |
| B3 PIR + padded OHTTP | no changed benchmark/PIR/OHTTP dependency | preserve historical 13/14 |
| B4 fixed transcript external | changed canonical runtime | rerun required, but not run after serial gate failure |
| B5 full strict | changed canonical runtime | rerun required, but not run after serial gate failure |
| 22 security negatives | recovery subset reaches changed durable runtime | historical 22/22 preserved; V12.2 revalidation not run after serial failure |
| SimplePIR benchmark | source/binary/protocol unchanged | preserve historical benchmark |
| corpus coverage | extractor/corpus dependencies unchanged | preserve frozen 894/473/3 result |
| profile qualification | changed canonical runtime | rerun required, not run after serial failure |

Consequently the current V12.2 system gate cannot use historical B4/B5 or profile results as post-repair validation. No unaffected experiment was rerun for cosmetic consistency.

# V10A superseded execution-harness audit

Status: `FROZEN_BUT_NOT_EXECUTED_SUPERSEDED_V10A`

This audit supersedes the selected experiments, not the accepted V9/V9.1 system or public-profile design. No selected V10A source site, semantic case, structural arm, or private workload was executed while preparing V10A.1.

| Item | Audit conclusion |
|---|---|
| profile freeze | accepted |
| seed construction | accepted |
| prior-case exclusion | accepted |
| selected cases | never executed |
| structural/size projection | accepted |
| semantic execution harness | incomplete: it compared caller-created dictionaries and did not create them through native and canonical execution |

Permanent exclusions added: 32 V10A semantic cases/source sites and 20 V10A structural arms. The full machine-readable exclusion set is `V10_1_SEMANTIC_EXCLUSION_SET.json`; structural sequence signatures are included there as a separate namespace.

Frozen input hashes:

- `CANONICAL_SEMANTIC_HOLDOUT_V10_FREEZE.json`: `6699fe315ab35ab059c7e2e44e09f24a36ed07b047c1646d491f2daacaf10f9d`
- `STRUCTURAL_SIZE_HOLDOUT_V10_FREEZE.json`: `2022c655161d339a2751637f997fa62a68c0bc600427d5d4adf9a17281a72827`

These files were read only. Their runtime outcomes remain unknown and must not be obtained later.

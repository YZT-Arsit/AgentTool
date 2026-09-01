# V12 P10 timing-distinguishability sentinel V3 freeze

Methodology baseline: `63792088161deb6b1ccd3c4b4cb28babbf72f3ec`.
Committed execution source: `71b45fc84515038ef8c3ba16bf18f8a216f2cd11`.

The complete identity manifest was frozen before the first protected session. It contains eight physical task/framework coordinates, 315 matched blocks per coordinate, 189 planned TRAIN blocks, 126 planned EVAL blocks, and exactly 5,040 one-use session identities. Workload blocks use the fresh range `B6000..B6314`. Within-pair class order, outer coordinate order, TRAIN/EVAL assignment, selection priority, model/bootstrap/randomization seeds, features, and analysis hashes are frozen.

The exclusion inventory contains 12,084 prior development identities. It includes all identities from both prior P10 sentinel manifests—including all 5,040 planned identities in the campaign closed at `63bdd948dc5364cf3bdfa85bcc5170f5c5d5712b`—plus functional, methodology, RCA, and other development ledgers. New identity overlap is zero.

Relay raw widths are `506,505,506,505,506`, and the complete Relay feature width is 2,589. Failure status, absolute wall clock, experiment ordinal, block ID, operation identity, and private diagnostics are excluded from classifier features.

Manifest payload SHA-256: `a4ce6199c3bc703cd954cdf9be6146d82d7e7b1d4f2fe658877e9e9d0ef288f9`.
Manifest file SHA-256: `89a4e8ba52a88fa6cac4b94f61c47eb32b7aa1f028be3b9c436613a966dc96c9`.

At freeze time: protected sessions 0, classifier training 0, AUC calculations 0, bootstrap runs 0, retries 0.

# Historical evidence integrity and platform disposition

All nine artifacts referenced by the prior missing-file failures are present in the authoritative repository copy and are hash-bound above. The Linux execution bundle still lacks all nine; that prior failure remains preserved. Because the tests only read completed V2/V4/crypto result trees and no selected V12 runtime imports them, they are historical evidence integrity checks rather than executable current-runtime correctness.

The Stage-9 approval-path node requires a historical Windows `.venv-stage9/Scripts/python.exe`. The selected V12 platform is Linux and has no dependency on that layout. Its status is `NOT_RUN_PLATFORM_SPECIFIC_HISTORICAL`; no fake Windows path was created.

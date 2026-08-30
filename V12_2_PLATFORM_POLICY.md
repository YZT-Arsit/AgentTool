# V12.2 target-platform policy

This policy was frozen at base commit `bdbb35b873ebf5c660b288b391abe320c3963d99` before any V12.2 decisive execution. The primary confirmatory platform is the authorized offline Linux host. Windows remains development and portability evidence; its retained durable-I/O failures are not relabeled as Linux results.

Class A contains every current V12 execution-reachable runtime or contract test and must execute without skips on Linux. Class B contains historical V1-V11 evidence audits whose old result trees are not part of the selected V12 runtime. Class C contains Windows-only historical layout or portability tests. Classification is fixed per exact pytest node in `V12_2_TEST_CLASSIFICATION.json`; no outcome, seed, retry, xfail, or added skip can alter it.

This platform policy changes neither the public profile nor any privacy claim. Timing privacy remains open/not tested, packet-level timing remains open, and hardware TEE validation remains not tested.

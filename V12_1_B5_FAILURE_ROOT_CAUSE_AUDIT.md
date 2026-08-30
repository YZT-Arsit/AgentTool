# V12.1 retained B5 failure root-cause audit

This is a read-only analysis of the immutable V12 failure trees. No historical identity was rerun.

- Count 25 / repetition 3 missed slot **229** with **5.881214 ms** launch slip. This exceeded the 3 ms diagnostic tolerance but remained below the 10 ms next-slot deadline. It emitted 355/356 Relay events; all 25 real actions, provider calls, and results completed.
- Count 50 / repetitions 7, 16, and 25 submitted and PIR-recovered all 50 operations, but only 43, 42, and 40 were accepted/admitted. The first divergences are operations 44, 43, and 41 respectively, all at `ACTION_ACCEPTED`, followed by explicit `PROFILE_ADMISSION_CLOSED`. There was no scheduler miss, provider omission among admitted actions, pending accepted result, or silent committed-result loss.

The private trajectory timestamps localize the delay further. PIR recovery took 0.8–6.9 ms, while otherwise regular result progress was interrupted by 581.605–1,316.555 ms waits (rep 7: 1,316.555/78.031 ms; rep 16: 581.605/807.050 ms; rep 25: 1,313.421/227.841 ms). Source audit found that effect-recovery and ready-queue transitions synchronously rewrote, `fsync`ed, and renamed growing JSON snapshots on the request/result path. Fresh Windows probes reproduced the stalls; fresh Linux probes did not. This is the first private lifecycle divergence that explains the later admission closure.

The count-50 failures are therefore admission-horizon failures caused upstream by synchronous durable-state I/O stalls after successful private resolution, not scheduler, PIR, provider omission, result loss, or DeliveryLedger failure. The exact operation-ID sets and causal checks are frozen in the JSON audit.

# V12 long-run failure-budget decomposition

Status: `INSUFFICIENT_EVIDENCE`

This audit inspected only private semantic/control artifacts belonging to `DEV-TAD-P10-T7-MS-SENTINEL-B0075-C1`. It did not inspect Registry/Relay observer timing distributions. The identity was not reexecuted.

## What is mechanically observed

The Python lifecycle record places the first intent 8.985796 ms after its `SESSION_T0`/`SESSION_READY` boundary and descriptor recovery at 30.917260 ms. That lifecycle boundary is earlier than the Go scheduled public slot-1 T0 and is therefore not silently conflated with it.

The first action was accepted and admitted in public round 1. Relative to the Go scheduled public T0, the provider request began at 3895.950836 ms and returned at 3898.427336 ms. The provider transport itself took 2.648768 ms, so the unexplained delay preceded provider request emission; increasing the 50 ms provider-completion bound would not describe this event correctly.

`RESULT_COMMITTED` and `READY_PUBLISHED` are present, and the durable result queue contains the operation in `READY` state. Neither stage has a monotonic timestamp. The queue's `published_ns` uses wall-clock Unix time and cannot be aligned mechanically with the two recorded monotonic origins.

The final result-capacity slot is derived as slot 505. Its observed effective eligibility was 5084.102112 ms after Go public T0. Terminal slot 506 dispatched at 5094.241865 ms. The result was nevertheless still pending at session completion.

The second Agent-as-Tool intent was recorded 6420.945812 ms after the Python lifecycle boundary. Its descriptor-attempt timestamp is unavailable, but it necessarily occurred later and produced `PIR_REAL_RESOLUTION_ADMISSION_CLOSED`.

## Missing fields

Exact timestamps are unavailable for action submission to Go, action acceptance/admission, worker completion, `READY_PUBLISHED`, result-slot eligibility, framework-visible failure, public `SESSION_COMPLETE`, and the second descriptor attempt. Consequently, the complete causal budget and the exact minimum additional horizon cannot be recovered.

## Strict lower bound that does not require the missing timestamps

The PIR cover schedule starts before the Python lifecycle `SESSION_T0` record. Therefore the second intent occurred more than 6420.945812 ms after the PIR cover origin. The frozen cutoff requires:

```
H > second_descriptor_attempt_elapsed + K*PIR_period + PIR_completion_bound + 1
H > 6420.945812 + 6*60 + 50 + 1
H > 6831.945812 ms
```

The true descriptor attempt was later than the intent, so the exact requirement is larger. Relative to H4500, the strict additional-horizon lower bound is greater than 2331.945812 ms; `MINIMUM_ADDITIONAL_ADMISSION_HORIZON_MS` remains `UNKNOWN`.

Admission closure is independently established. Go's scheduled public T0 was at most 384.993104 ms after the earlier `T0_ASSIGNED` setup record; `SESSION_READY` and the Python lifecycle boundary occurred later. Therefore the second intent was at least 6035.952708 ms after Go public T0, beyond even H6000 admission.

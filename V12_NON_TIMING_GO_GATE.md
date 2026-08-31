# V12 non-timing Go regression gate

All **70/70** frozen non-timing Go tests passed. Coverage includes provider-result classification, authorization, operation/result binding, WAL and ready-queue recovery, replay rejection, OHTTP/BHTTP codecs, authenticated public headers and slots, fixed-width representation, and fail-closed route/admission checks.

Eleven tests whose decisive condition is cadence, launch slip, a public deadline, affinity, or profile capacity were excluded by name before execution. No scheduler outcome was reinterpreted.

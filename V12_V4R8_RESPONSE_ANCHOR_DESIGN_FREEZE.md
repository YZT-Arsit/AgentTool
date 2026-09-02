# V12 V4R8 response public-anchor design freeze

V4R8 makes exactly one post-outcome development change: the planned Gateway response clock no longer depends on per-slot Gateway request arrival.

```text
OLD:
F_i = max(E_i + rho,
          gateway_request_arrival_i + L_response,
          F_(i-1) + Delta)

V4R8:
F_1 = E_1 + rho
F_i = max(E_i + rho,
          F_(i-1) + Delta)

G_i = F_i - L_response
S_i = max(F_i, S_(i-1) + Delta)
```

Gateway request arrival remains recorded in the strengthened application-observer trace but is diagnostic/observable input only. It cannot alter `F_i`, `G_i`, or later planned response releases. A late request uses the original `G_i` cutoff and the existing V4R7 late-frame/no-catch-up rules.

All public numeric and utility parameters remain unchanged: H=4500 ms, B=200 ms, Delta=10 ms, M=50, R=521, Q=100, rho=30 ms, response preparation lead=20 ms, six response preparation workers, request=1079 bytes, and response=800 bytes.

No protected session, classifier fit, or AUC calculation occurred before this freeze.

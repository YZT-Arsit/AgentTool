# Baseline Matrix V7-OHTTP

This matrix was frozen before any RFC-wire confirmatory experiment. No such
experiment ran because the compatible offline backend is absent.

| ID | Path | Payload confidentiality | Target metadata | Size | Count/order/lifetime | Timing |
|---|---|---|---|---|---|---|
| B0 | DIRECT_PROTECTED_TLS | TLS | Tool/Agent destination exposed | natural | natural | natural |
| B1 | PIR_PLUS_DIRECT_TLS | PIR + TLS | Agent lookup private; direct action activation exposed | natural | natural | natural |
| B2 | OHTTP_UNSHAPED | intended RFC 9458 | Relay sees common Gateway, Gateway trusted | natural | natural | natural |
| B3 | OHTTP_PADDED | B2 + RFC 9292 padding | as B2 | fixed per public bucket | natural | natural |
| B4 | OHTTP_FIXED_TRANSCRIPT | B3 | as B2 | fixed | fixed nominal transcript | not claimed |
| B5 | V7_OHTTP_STRICT | unified SimplePIR + trusted module + OHTTP Gateway | intended strict route hiding | fixed | fixed | OPEN |
| B6 | V7_OHTTP_ENTERPRISE_EFFICIENT | hierarchical resolution + OHTTP external path | declared internal/external route leakage | profile-fixed | profile-fixed | OPEN |
| Legacy | LEGACY_CUSTOM_GATEWAY | custom AES-GCM development framing | common endpoint in local model | fixed | fixed | known noncanonical |

B2-B6 are specifications until RFC 9458 is integrated. The Legacy row cannot
stand in for them.


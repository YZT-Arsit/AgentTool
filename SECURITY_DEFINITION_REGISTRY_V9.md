# Registry Security Definition — V9

The registry game is unchanged from frozen V8. The selected Agent row/ID is
secret; the untrusted registry observes public PIR parameters and opaque
query/answer metadata. Official SimplePIR is the mechanism. Query generation,
fresh randomness, client state/hints, recovery, descriptor authentication, and
plaintext remain trusted.

V9 regression status: **PASS**. The post-OHTTP 1K smoke recovered 4/4
authenticated AgentDescriptorV7 rows. Two queries for the same index had
different raw server-visible query bytes. This smoke is a regression, not a new
cryptographic proof or replacement for frozen 100K evidence.


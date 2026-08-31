# Current cleanup/resource API audit

Production `V11EvidenceProviders` accepts `(cases, private_evidence_path=None)`, and `CanonicalOnlineSession.__enter__` deliberately supplies both arguments. That API is used to preserve bounded private provider diagnostics and is correct.

The previous fixture implemented only the old one-argument constructor. It was stale. The fixture now accepts and verifies the private evidence path while retaining the original direct assertion that a partial startup failure exits PIR/providers and clears both session references. No production, scheduler, profile, or timing behavior changed.

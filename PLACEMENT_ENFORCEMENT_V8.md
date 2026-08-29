# Placement Enforcement V8

Trusted resolution now requires an explicit `PrivacyProfile`; a string or
unknown value is rejected rather than downgraded.

- STRICT permits TRUSTED_MODULE_LOCAL and routes EXTERNAL through the common
  OHTTP Action Gateway. CLOUD_LOCAL is rejected unless its opaque route is in
  the explicit strict common/confidential broker set.
- CONFIDENTIAL_ENTERPRISE permits CLOUD_LOCAL only when declared in the
  confidential deployment policy and records internal/external route-class
  leakage.
- ENTERPRISE_EFFICIENT may permit CLOUD_LOCAL under an explicit policy flag and
  records `CLOUD_LOCAL_ACTION_CLASS` leakage.

Rules apply equally to Agent-service and Tool/external action routes. Negative
tests prove that unbrokered CLOUD_LOCAL Agent and Tool routes fail in STRICT,
unknown profile values fail, and unauthorized Tool capabilities fail.

Status: `PLACEMENT_ENFORCEMENT = PASS`.


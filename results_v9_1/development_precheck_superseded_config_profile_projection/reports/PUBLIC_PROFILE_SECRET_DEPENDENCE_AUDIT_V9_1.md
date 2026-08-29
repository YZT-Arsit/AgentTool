# Public-profile Secret-dependence Audit V9.1

| Field | Classification | Source | Active STRICT V9.1 |
|---|---|---|---|
| profile_id | USER_SELECTED_PRIVACY_PROFILE | `canonical_v9_1/profile.py:10` / `validate_profile_id` | True |
| admission_rounds | USER_SELECTED_PRIVACY_PROFILE | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| maximum_real_operations | USER_SELECTED_PRIVACY_PROFILE | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| total_rounds | USER_SELECTED_PRIVACY_PROFILE | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| round_period_ms | USER_SELECTED_PRIVACY_PROFILE | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| provider_completion_bound_ms | USER_SELECTED_PRIVACY_PROFILE | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| terminal_rounds | USER_SELECTED_PRIVACY_PROFILE | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| session_count | USER_SELECTED_PRIVACY_PROFILE | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| scheduled_public_lifetime | PUBLIC_POLICY | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| request_bhttp_bytes | PUBLIC_POLICY | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| response_bhttp_bytes | PUBLIC_POLICY | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| request_final_bytes | PUBLIC_POLICY | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| response_final_bytes | PUBLIC_POLICY | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| ohttp_key_id | CONSTANT_PUBLIC | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| kem_id | CONSTANT_PUBLIC | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| kdf_id | CONSTANT_PUBLIC | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| aead_id | CONSTANT_PUBLIC | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| config_epoch | CONSTANT_PUBLIC | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| relay_endpoint_class | CONSTANT_PUBLIC | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| gateway_endpoint_class | CONSTANT_PUBLIC | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| connection_policy | CONSTANT_PUBLIC | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| scheduled_start_policy | CONSTANT_PUBLIC | `canonical_v9_1/profile.py:141` / `strict_h50_profile` | True |
| go_plan_public_fields | PUBLIC_POLICY | `canonical_v9_1/profile.py:111` / `PublicCapacityProfile.go_plan_fields` | True |
| private_actual_real_actions | SECRET | `canonical_v9_1/runner.py:13` / `invoke_go_with_public_profile` | True |
| historical_v9_rounds/admission/maximum | SECRET_DEPENDENT_INVALID | `canonical_v9/runner.py:178` / `capacity_profile` | False |
| historical_v9_profile_id | SECRET_DEPENDENT_INVALID | `canonical_v9/runner.py:178` / `capacity_profile` | False |

The two SECRET_DEPENDENT_INVALID rows document the frozen V9 development path and are excluded from V9.1. No active STRICT V9.1 public field is secret-dependent.

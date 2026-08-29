from __future__ import annotations

from canonical_v9_1.profile import strict_h50_profile
from v10_holdout.harness import compare_semantic, compare_structural_pair, load_v10_profile, prefix_projection, validate_operation_ids


def _trace(profile, connection: str):
    return {"public_relay_events": [{
        "round": i, "profile_id": profile.profile_id, "ohttp_key_id": 7, "kem_id": 32,
        "kdf_id": 1, "aead_id": 1, "config_epoch": 3, "relay_endpoint": "LOCAL_RELAY",
        "gateway_endpoint": "LOCAL_GATEWAY", "relay_client_connection_id": connection,
        "relay_gateway_connection_id": connection + "g", "request_length": 1079,
        "response_length": 800,
    } for i in range(1, profile.total_rounds + 1)]}


def test_operation_id_rule_on_non_holdout_fixture():
    validate_operation_ids(["dev00000001", "dev00000002"])


def test_semantic_projection_rule_on_non_holdout_fixture():
    value = {
        "selected_logical_action": "tool.dev", "arguments": {"x": 1},
        "provider_visible_logical_request": {"route": "dev"}, "effect_count": 0,
        "operation_outcome_semantics": "READ_ONLY/SUCCESS", "result": "ok",
        "final_framework_visible_result_state": "ok",
    }
    assert compare_semantic(value, dict(value)) == "PASS"


def test_projection_and_prefix_on_synthetic_non_holdout_fixture():
    base = strict_h50_profile()
    profile = type(base)(**{**base.__dict__, "profile_id": "V9_1-STRICT-H50-P1"})
    a, b = _trace(profile, "ephemeral-a"), _trace(profile, "ephemeral-b")
    result = compare_structural_pair(a, b, profile, True, True)
    assert result == {"pair_status": "VALID", "structural": "PASS", "size": "PASS"}
    from canonical_v9_1.projection import strict_structural_projection
    assert len(prefix_projection(strict_structural_projection(a, profile), 10)["round_order"]) == 10


def test_v10_profile_adapter_changes_only_public_identifier():
    profile = load_v10_profile()
    assert profile.profile_id == "V10-STRICT-H50-C1"
    assert profile.total_rounds == 111 and profile.request_final_bytes == 1079

from __future__ import annotations

import base64
import json
import urllib.request

from canonical_v9_1.projection import strict_size_projection, strict_structural_projection
from v11_full_scope.canonical import V11EvidenceProviders
from v11_full_scope.fixtures import tool_case
from v11_4.profile import selected_profile


def test_private_provider_evidence_records_lifecycle_without_arguments(tmp_path):
    case = tool_case("DEV-PC-provider-evidence", "OpenAI Agents SDK")
    evidence_path = tmp_path / "private_provider_evidence.json"
    with V11EvidenceProviders({case.operation_id: case}, evidence_path) as providers:
        protected = json.dumps({"arguments": case.arguments}).encode()
        request_body = json.dumps(
            {
                "operation_id": case.operation_id,
                "payload": base64.b64encode(protected).decode(),
            }
        ).encode()
        request = urllib.request.Request(
            providers.endpoints["route-tool-read"],
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 200
            assert json.loads(response.read())["status"] == "OK"

    rows = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert len(rows) == 1
    row = rows[0]
    assert row["operation_id"] == case.operation_id
    assert row["route_handle"] == "route-tool-read"
    assert row["request_received"] is True
    assert row["request_decoded_successfully"] is True
    assert row["handler_logical_completion_monotonic_ns"] > 0
    assert row["http_response_status_emitted"] == 200
    assert row["encoded_response_bytes"] > 0
    assert row["response_write_success"] is True
    assert row["handler_elapsed_ns"] > 0
    encoded = json.dumps(rows, sort_keys=True)
    assert "protected_arguments" not in encoded
    assert case.arguments["city"] not in encoded


def test_provider_diagnostics_do_not_change_public_projections():
    profile = selected_profile(10, 3000)
    events = []
    for round_number in range(1, profile.total_rounds + 1):
        events.append(
            {
                "profile_id": profile.profile_id,
                "round": round_number,
                "session": 1,
                "ohttp_key_id": profile.ohttp_key_id,
                "kem_id": profile.kem_id,
                "kdf_id": profile.kdf_id,
                "aead_id": profile.aead_id,
                "config_epoch": profile.config_epoch,
                "relay_endpoint": profile.relay_endpoint_class,
                "gateway_endpoint": profile.gateway_endpoint_class,
                "relay_client_connection_id": "client-connection",
                "relay_gateway_connection_id": "gateway-connection",
                "client_http_version": "HTTP/2.0",
                "gateway_http_version": "HTTP/2.0",
                "request_length": profile.request_final_bytes,
                "response_length": profile.response_final_bytes,
            }
        )
    trace = {"public_relay_events": events}
    before_structural = strict_structural_projection(trace, profile)
    before_size = strict_size_projection(trace, profile)
    trace["provider_diagnostics"] = [
        {
            "operation_id": "private-operation",
            "route_handle": "private-route",
            "class": "PROVIDER_TRANSPORT_ERROR",
            "error": "private diagnostic",
        }
    ]
    assert strict_structural_projection(trace, profile) == before_structural
    assert strict_size_projection(trace, profile) == before_size
    assert "private-operation" not in json.dumps(before_structural, sort_keys=True)

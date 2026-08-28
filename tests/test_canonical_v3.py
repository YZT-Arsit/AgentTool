from __future__ import annotations

import json
import os
import csv
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from agent_control_virtualization.ir import AgentCapsule, ControlEvent, ControlRow, Opcode
from canonical_v3.runner import run_canonical_gateway
from canonical_v3.workflows import llm_read_tool, logical_handoff
from cloud_slot_proxy.proxy import FORBIDDEN_PROXY_FIELDS, ProxyConfig, assert_public_proxy_schema
from privacy_kernel.control import ControlKernel
from privacy_kernel.protocol import (ACTION_TOOL, CanonicalProfile,
                                     EnvelopeCodec, PUBLIC_HEADER,
                                     parse_public_header)


ROOT = Path(__file__).resolve().parents[1]


def profile(sessions: int = 6) -> CanonicalProfile:
    return CanonicalProfile("CANONICAL_V3_TEST", 1024, 3, sessions, 40_000_000,
                            40_000_000, 8_000_000, 350_000_000, 60_000_000)


def test_proxy_schema_has_only_public_configuration() -> None:
    assert_public_proxy_schema()
    names = set(ProxyConfig.__dataclass_fields__)
    assert names == {"address", "public_profile", "host_log_path"}
    assert not names & FORBIDDEN_PROXY_FIELDS


def test_trusted_encoder_hides_plaintext_and_authenticates_public_header() -> None:
    codec = EnvelopeCodec(bytes(range(16)), profile())
    frame = codec.encode_request(0, 1, action=ACTION_TOOL, provider=8,
                                 operation_id="private-operation", payload=b"private-payload")
    assert len(frame) == 1024
    assert b"private-operation" not in frame
    assert b"private-payload" not in frame
    header = parse_public_header(frame)
    assert (header.session, header.slot, header.profile_id) == (0, 1, profile().profile_id)
    for offset in (0, 2, 4, 8, 12):
        changed = bytearray(frame)
        changed[offset] ^= 1
        try:
            parse_public_header(bytes(changed))
        except ValueError:
            continue
        nonce_at = PUBLIC_HEADER.size
        with pytest.raises(InvalidTag):
            AESGCM(bytes(range(16))).decrypt(
                bytes(changed[nonce_at:nonce_at + 12]),
                bytes(changed[nonce_at + 12:]), bytes(changed[:nonce_at]))


def test_pending_result_does_not_advance_control_state() -> None:
    fixture = llm_read_tool()
    kernel = fixture.kernel()
    descriptor = kernel.tick()
    assert descriptor is not None
    assert kernel.state.current_state == 0
    assert kernel.tick() is None
    assert kernel.state.current_state == 0


def test_handoff_changes_only_trusted_logical_state() -> None:
    fixture = logical_handoff()
    kernel = fixture.kernel()
    assert kernel.tick() is None
    assert kernel.state.logical_agent_id == 21
    assert kernel.state.pending_lookup is None
    public_identity = "CloudSlotProxy->CommonActionGatewayV2"
    assert "21" not in public_identity


def test_canonical_entrypoint_has_no_mock_or_oram_reachability() -> None:
    source = (ROOT / "canonical_v3/runner.py").read_text(encoding="utf-8")
    assert "MockPrivateLookup" not in source
    assert "path_oram" not in source.lower()
    assert "stage11" not in source.lower()
    assert "gateway_v2.runner" not in source
    assert "gateway-cloud-client" not in source
    assert '"--key",' not in source
    assert '"--key-file"' in source


def test_real_pir_schedule_fed_the_control_kernel() -> None:
    result = json.loads((ROOT / "results_canonical_v3/phase2_pir_smoke/phase2_result.json").read_text(encoding="utf-8"))
    assert result["audit"]["backend"] == "OFFICIAL_SIMPLEPIR_FULL_PREPROCESSING"
    assert result["audit"]["correct_queries"] == 3
    assert result["audit"]["real_queries"] == 1
    assert result["audit"]["dummy_queries"] == 2
    assert result["audit"]["fresh_queries"] is True
    assert result["audit"]["server_trace_has_private_index"] is False
    assert result["control_transition_after_pir"] is True


def test_corpus_and_semantic_audits_preserve_negative_results() -> None:
    with (ROOT / "CORPUS_IR_COVERAGE.csv").open(newline="", encoding="utf-8") as handle:
        coverage = next(row for row in csv.DictReader(handle)
                        if row["framework"] == "ALL" and row["behavior_kind"] == "ALL")
    assert int(coverage["total"]) == 7386
    assert int(coverage["unsupported"]) == 3812
    assert float(coverage["coverage"]) < 0.5
    with (ROOT / "SEMANTIC_FIDELITY_RESULTS.csv").open(newline="", encoding="utf-8") as handle:
        semantic = list(csv.DictReader(handle))
    assert len(semantic) == 72
    assert sum(row["equivalent"] == "True" for row in semantic) == 54
    assert all(row["equivalent"] == "False" for row in semantic if row["stratum"] == "openai_tool")


@pytest.mark.skipif(os.environ.get("SKIP_CANONICAL_INTEGRATION") == "1", reason="explicit local opt-out")
def test_canonical_gateway_result_consumer_and_fixed_schedule(tmp_path: Path) -> None:
    fixture = llm_read_tool()
    try:
        result = run_canonical_gateway(ROOT, tmp_path / "canonical", profile(), fixture.kernel())
    except OSError as exc:
        if getattr(exc, "winerror", None) == 4551:
            pytest.skip("NOT_COMPLETED_ENVIRONMENT: Windows Application Control blocked the local Pacer executable")
        raise
    assert result["returned"] is True
    assert result["real_heavy_operations"] == fixture.expected_heavy_operations
    assert result["dummy_heavy_operations"] == 0
    assert result["effect_count"] == fixture.expected_effects
    assert result["delivered_results"] == fixture.expected_heavy_operations
    assert result["one_persistent_tunnel"] is True
    assert result["key_on_command_line"] is False
    assert not (tmp_path / "canonical/trusted_gateway.key").exists()
    assert len({result["worker_pid"], result["pacer_pid"], result["proxy_pid"],
                *result["provider_pids"]}) == 6
    public = [json.loads(line) for line in
              (tmp_path / "canonical/agentcloud_public_trace.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(public) == profile().sessions * profile().slots * 2
    assert {row["frame_bytes"] for row in public} == {profile().frame_bytes}
    assert {row["destination"] for row in public} == {"CommonActionGatewayV2"}
    assert "logical_agent" not in json.dumps(public).lower()

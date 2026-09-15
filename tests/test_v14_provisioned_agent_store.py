from __future__ import annotations

from dataclasses import replace

import pytest

from v14_provisioned_agents.artifact import (
    ArtifactValidationError,
    PIR_RECORD_BYTES,
    ProvisionedAgentArtifactCodec,
)
from v14_provisioned_agents.fixtures import (
    SCALE_RECORDS,
    STORE_EPOCH,
    functional_artifacts,
    make_artifact,
    scale_row_for_agent,
)
from v14_provisioned_agents.loader import AgentLoader
from v14_provisioned_agents.models import AgentFramework, PIRRowHandle
from v14_provisioned_agents.psi import APSIError, encode_idle_item, encode_real_item, require_real_apsi
from v14_provisioned_agents.simplepir import require_real_simplepir


KEY = bytes.fromhex("50" * 32)


def test_artifact_round_trip_fixed_width_and_binding() -> None:
    codec = ProvisionedAgentArtifactCodec(KEY, STORE_EPOCH)
    for artifact in functional_artifacts():
        row = codec.encode(artifact)
        assert len(row) == PIR_RECORD_BYTES == 1024
        assert codec.decode(row, artifact.canonical_agent_id) == artifact
        with pytest.raises(ArtifactValidationError, match="AgentID binding"):
            codec.decode(row, artifact.canonical_agent_id + 99)


def test_artifact_authentication_and_remote_service_fields_fail_closed() -> None:
    codec = ProvisionedAgentArtifactCodec(KEY, STORE_EPOCH)
    artifact = make_artifact(11, AgentFramework.OPENAI_AGENTS_SDK)
    row = bytearray(codec.encode(artifact))
    row[-1] ^= 1
    with pytest.raises(ArtifactValidationError, match="authentication"):
        codec.decode(bytes(row), 11)
    with pytest.raises(ValueError, match="remote Agent-service"):
        replace(artifact, runtime_policy={"private_execution_handle": "forbidden"}).validated()


def test_row_handle_is_minimal_fixed_width_and_versioned() -> None:
    value = PIRRowHandle(row_index=71, store_epoch=STORE_EPOCH)
    assert len(value.encode()) == 32
    assert PIRRowHandle.decode(value.encode()) == value


def test_scale_mapping_is_bijective_and_idle_item_is_domain_separated() -> None:
    rows = {scale_row_for_agent(agent_id) for agent_id in range(1, SCALE_RECORDS + 1)}
    assert rows == set(range(SCALE_RECORDS))
    idle = encode_idle_item()
    assert idle not in {encode_real_item(agent_id) for agent_id in range(1, SCALE_RECORDS + 1)}


@pytest.mark.parametrize("framework", list(AgentFramework))
def test_loader_constructs_real_framework_native_agent(framework: AgentFramework) -> None:
    artifact = make_artifact(31, framework)
    loaded = AgentLoader().load(artifact)
    assert loaded.run() == artifact.runtime_policy["expected_output"]
    if framework is AgentFramework.OPENAI_AGENTS_SDK:
        from agents import Agent
    else:
        from agent_framework import Agent
    assert isinstance(loaded.native_agent, Agent)
    assert loaded.evidence()["remote_agent_service_invocations"] == 0


@pytest.mark.parametrize("framework", list(AgentFramework))
def test_nested_agent_is_loaded_as_real_framework_agent_tool(framework: AgentFramework) -> None:
    child = make_artifact(42, framework, role="child")
    parent = make_artifact(41, framework, role="parent", child_id=42)
    loader = AgentLoader()
    loaded = loader.load(parent, [loader.load(child)])
    assert loaded.run() == parent.runtime_policy["expected_output"]
    assert loaded.evidence()["loaded_child_count"] == 1


def test_production_guards_reject_noncryptographic_backends() -> None:
    with pytest.raises(APSIError, match="REAL_PSI_REQUIRED"):
        require_real_apsi(object())
    with pytest.raises(RuntimeError, match="REAL_SIMPLEPIR_REQUIRED"):
        require_real_simplepir(object())


def test_v14_path_has_no_remote_agent_service_semantics() -> None:
    from pathlib import Path

    forbidden = (
        "GatewayAgentDestination",
        "private_execution_handle",
        "REAL_AGENT_SERVICE",
    )
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (Path(__file__).parents[1] / "v14_provisioned_agents").rglob("*.py")
    )
    # The validator's deny-list names one legacy field; no executable V14 type/path may use it.
    scrubbed = sources.replace('"private_execution_handle",', "")
    for token in forbidden:
        assert token not in scrubbed
    gateway = (Path(__file__).parents[1] / "v14_provisioned_agents" / "gateway.py").read_text()
    assert "SUBMIT_RESOLVED_ACTION" in gateway
    assert '"REAL_EXTERNAL_HTTP"' in gateway
    assert "REAL_AGENT_SERVICE" not in gateway

from __future__ import annotations

from .models import AgentFramework, ProvisionedAgentArtifactV1


STORE_EPOCH = 20260915
SCALE_RECORDS = 100_000
DUMMY_PIR_ROW = SCALE_RECORDS


def scale_row_for_agent(agent_id: int, records: int = SCALE_RECORDS) -> int:
    """Public, bijective test-store layout; deliberately not AgentID == row."""
    if not 1 <= agent_id <= records:
        raise ValueError("scale-corpus AgentID outside 1..N")
    return ((agent_id - 1) * 65_537 + 17) % records


def make_artifact(
    agent_id: int,
    framework: AgentFramework,
    *,
    role: str = "ordinary",
    child_id: int | None = None,
    synthetic_scale: bool = False,
) -> ProvisionedAgentArtifactV1:
    short = "oai" if framework is AgentFramework.OPENAI_AGENTS_SDK else "maf"
    children = () if child_id is None else (child_id,)
    return ProvisionedAgentArtifactV1(
        canonical_agent_id=agent_id,
        framework=framework,
        name=f"OAE-{short}-{role}-{agent_id}",
        instructions=(
            "Return the deterministic fixture result after applying the declared "
            "private Agent capability."
        ),
        model_reference="OAE_DETERMINISTIC_FIXTURE_V1",
        model_configuration={"temperature": 0, "provider": "deterministic-fixture"},
        tool_capability_refs=("fixture.echo.v1",),
        sub_agent_ids=children,
        runtime_policy={
            "expected_output": f"v14:{short}:{role}:{agent_id}:ok",
            "execution_boundary": "trusted-runtime",
            "synthetic_scale_record": synthetic_scale,
        },
        publisher_id="oae-development-publisher",
        publisher_version=1,
        store_epoch=STORE_EPOCH,
    )


def functional_artifacts() -> tuple[ProvisionedAgentArtifactV1, ...]:
    values: list[ProvisionedAgentArtifactV1] = []
    for framework, base in (
        (AgentFramework.OPENAI_AGENTS_SDK, 101),
        (AgentFramework.MICROSOFT_AGENT_FRAMEWORK, 201),
    ):
        values.extend(
            [
                make_artifact(base, framework, role="provisioned-ordinary"),
                make_artifact(base + 1, framework, role="provisioned-nested", child_id=base + 2),
                make_artifact(base + 2, framework, role="provisioned-child"),
                make_artifact(1_000_000 + base, framework, role="unprovisioned-ordinary"),
                make_artifact(
                    1_000_001 + base,
                    framework,
                    role="unprovisioned-nested",
                    child_id=1_000_002 + base,
                ),
                make_artifact(1_000_002 + base, framework, role="unprovisioned-child"),
            ]
        )
    return tuple(values)


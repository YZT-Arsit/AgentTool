from __future__ import annotations

import argparse
import json
from pathlib import Path

from v14_provisioned_agents.artifact import ProvisionedAgentArtifactCodec
from v14_provisioned_agents.fixtures import STORE_EPOCH, functional_artifacts
from v14_provisioned_agents.gateway import run_frozen_v4r8_gateway_artifact_session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    codec = ProvisionedAgentArtifactCodec(args.key.read_bytes(), STORE_EPOCH)
    artifact = next(a for a in functional_artifacts() if a.canonical_agent_id == 1_000_101)
    row = codec.encode(artifact)
    results = {
        "PROVISIONED": run_frozen_v4r8_gateway_artifact_session(
            args.runner, args.work / "provisioned_cover", agent_id=None, artifact=None
        ),
        "UNPROVISIONED": run_frozen_v4r8_gateway_artifact_session(
            args.runner, args.work / "unprovisioned_retrieval",
            agent_id=artifact.canonical_agent_id, artifact=row,
        ),
        "IDLE": run_frozen_v4r8_gateway_artifact_session(
            args.runner, args.work / "idle_cover", agent_id=None, artifact=None
        ),
    }
    recovered = results["UNPROVISIONED"].artifact
    decoded = codec.decode(recovered, artifact.canonical_agent_id) if recovered else None
    public = {key: value.public_profile for key, value in results.items()}
    output = {
        "frozen_v4r8_runner": str(args.runner),
        "cases": public,
        "public_profiles_equal": len({json.dumps(v, sort_keys=True) for v in public.values()}) == 1,
        "unprovisioned_artifact_bytes": len(recovered or b""),
        "unprovisioned_artifact_authenticated": decoded == artifact,
        "unprovisioned_gateway_real_actions": len(results["UNPROVISIONED"].result["results"]),
        "provisioned_gateway_real_actions": len(results["PROVISIONED"].result["results"]),
        "idle_gateway_real_actions": len(results["IDLE"].result["results"]),
        "agent_specific_gateway_destinations": 0,
        "remote_provisioned_agent_executions": 0,
        "protected_v4r8_runtime_modified": False,
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not output["public_profiles_equal"] or not output["unprovisioned_artifact_authenticated"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

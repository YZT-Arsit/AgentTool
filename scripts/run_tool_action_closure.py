from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from agent_control_virtualization.ir import AgentCapsule
from cryptographic_closure.tool_and_action import (
    ToolBoundary,
    run_action_type,
    run_tool_sequences,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run action- and Tool-boundary closure experiments.")
    parser.add_argument(
        "--capsule-log",
        type=Path,
        default=Path("results_crypto_closure/scale_100000/run4/client_recovered_records.jsonl"),
    )
    parser.add_argument("--output", type=Path, default=Path("results_crypto_closure/tool_action"))
    parser.add_argument("--skip-action", action="store_true")
    parser.add_argument("--skip-tool", action="store_true")
    args = parser.parse_args()

    recovered = json.loads(args.capsule_log.read_text(encoding="utf-8").splitlines()[0])
    capsule = AgentCapsule.deserialize(base64.b64decode(recovered["record_base64"]))
    with ToolBoundary() as boundary:
        action = [] if args.skip_action else run_action_type(
            capsule, boundary, args.output / "ACTION_TYPE_ATTACK_RESULTS.csv"
        )
        tool = []
        if not args.skip_tool:
            _, tool = run_tool_sequences(boundary, args.output / "TOOL_MULTIRROUND_RESULTS.csv")
    print(json.dumps({"action_rows": len(action), "tool_attack_rows": len(tool)}, indent=2))


if __name__ == "__main__":
    main()

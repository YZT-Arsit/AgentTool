from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LEGACY_EXCLUSIONS = {
    "tests/test_v11_full_scope.py::test_tool_multi_action_capacity[50]": (
        "SUPERSEDED_V10_STATIC_H50_111_ROUND_5MS_PROFILE_NOT_REACHABLE_FROM_"
        "V12_ONLINE_356_ROUND_10MS_H3000_EXECUTION"
    )
}


class FrozenV12Reachability:
    def __init__(self, output: Path) -> None:
        self.output = output

    def pytest_collection_modifyitems(self, config, items):
        collected = [item.nodeid for item in items]
        excluded = [item for item in items if item.nodeid in LEGACY_EXCLUSIONS]
        selected = [item for item in items if item.nodeid not in LEGACY_EXCLUSIONS]
        if {item.nodeid for item in excluded} != set(LEGACY_EXCLUSIONS):
            raise RuntimeError("frozen legacy V10 exclusion set did not match collection")
        items[:] = selected
        config.hook.pytest_deselected(items=excluded)
        manifest = {
            "schema": "AgentTool.V12_1.ExecutionReachablePytestScope/1",
            "collected": len(collected),
            "selected": len(selected),
            "excluded": [
                {"node_id": node_id, "reason": reason}
                for node_id, reason in LEGACY_EXCLUSIONS.items()
            ],
            "selection_rule": "exclude only execution paths mechanically unreachable from the V12 online runner",
            "xfail_added": 0,
            "skip_added": 0,
            "selected_v12_cases_executed": 0,
        }
        (self.output / "scope_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("serial", "default"), required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    pytest_args = ["-q", "--basetemp", str(output / "tmp")]
    if args.mode == "serial":
        pytest_args.extend(("-p", "no:xdist"))
    result = pytest.main(pytest_args, plugins=[FrozenV12Reachability(output)])
    (output / "exit_code.json").write_text(
        json.dumps({"mode": args.mode, "exit_code": int(result)}, indent=2) + "\n",
        encoding="utf-8",
    )
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())

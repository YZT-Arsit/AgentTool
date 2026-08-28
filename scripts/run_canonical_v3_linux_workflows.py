from __future__ import annotations

import csv
import json
from pathlib import Path

from canonical_v3.runner import run_canonical_gateway
from canonical_v3.workflows import llm_effect_tool, llm_read_tool, logical_handoff
from privacy_kernel.protocol import CanonicalProfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results_canonical_v3" / "linux_workflows"


def profile(name: str) -> CanonicalProfile:
    return CanonicalProfile(name, 1024, 3, 6, 40_000_000, 40_000_000,
                            8_000_000, 350_000_000, 60_000_000)


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for fixture in (llm_read_tool(), llm_effect_tool(), logical_handoff()):
        kernel = fixture.kernel()
        result = run_canonical_gateway(
            ROOT, OUTPUT / fixture.name.lower(),
            profile(f"CANONICAL_V3_{fixture.name}"), kernel,
        )
        row = {
            "workflow": fixture.name,
            "returned": result["returned"],
            "expected_heavy_operations": fixture.expected_heavy_operations,
            "real_heavy_operations": result["real_heavy_operations"],
            "dummy_heavy_operations": result["dummy_heavy_operations"],
            "expected_effects": fixture.expected_effects,
            "effect_count": result["effect_count"],
            "delivered_results": result["delivered_results"],
            "public_frames_each_direction": result["public_frames_each_direction"],
            "one_persistent_tunnel": result["one_persistent_tunnel"],
            "logical_agent_id_private": result["logical_agent_id_private"],
            "failure_class": kernel.state.failure_class,
            "sanitized_final_result": kernel.state.sanitized_result.decode("utf-8"),
            "semantic_equivalence": (
                result["returned"]
                and result["real_heavy_operations"] == fixture.expected_heavy_operations
                and result["effect_count"] == fixture.expected_effects
                and result["dummy_heavy_operations"] == 0
            ),
        }
        rows.append(row)
    with (OUTPUT / "workflow_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "workflow_results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()

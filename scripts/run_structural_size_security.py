from __future__ import annotations

import csv
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from canonical_v3.runner import run_canonical_gateway
from canonical_v3.workflows import (llm_effect_tool, llm_read_tool,
                                    llm_read_tool_variant, logical_handoff,
                                    private_branch)
from privacy_kernel.protocol import CanonicalProfile


DEFAULT_OUTPUT = ROOT / "results_canonical_v3" / "linux_structural_size"
FORBIDDEN = ("logical_agent", "provider", "operation_id", "opcode", "payload", "result", "key")


def profile() -> CanonicalProfile:
    return CanonicalProfile("CANONICAL_V3_STRUCTURAL_SIZE", 1024, 3, 6,
                            40_000_000, 40_000_000, 8_000_000,
                            350_000_000, 60_000_000)


def load_public(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def projection(rows: list[dict[str, object]]) -> tuple[tuple[object, ...], ...]:
    """Structural/size view only; timing is a separate unresolved property."""
    return tuple((row["direction"], row["session"], row["slot"],
                  row["frame_bytes"], row["destination"]) for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--extended", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    signatures: dict[str, tuple[tuple[object, ...], ...]] = {}
    fixtures = [llm_read_tool(), llm_effect_tool(), logical_handoff()]
    if args.extended:
        fixtures.extend([
            llm_read_tool_variant(41, 4101, "READ_ALPHA"),
            llm_read_tool_variant(42, 4201, "READ_BETA"),
            private_branch(False), private_branch(True),
        ])
    for fixture in fixtures:
        case = output / fixture.name.lower()
        result = run_canonical_gateway(ROOT, case, profile(), fixture.kernel())
        public = load_public(case / "agentcloud_public_trace.jsonl")
        encoded = json.dumps(public, sort_keys=True).lower()
        signature = projection(public)
        signatures[fixture.name] = signature
        rows.append({
            "workflow": fixture.name,
            "private_agent_id": fixture.initial_agent_id,
            "private_action_shape": fixture.name,
            "public_profile_id": result["profile_id"],
            "public_events": len(public),
            "request_events": sum(item["direction"] == "REQUEST" for item in public),
            "response_events": sum(item["direction"] == "RESPONSE" for item in public),
            "frame_bytes_min": min(int(item["frame_bytes"]) for item in public),
            "frame_bytes_max": max(int(item["frame_bytes"]) for item in public),
            "destinations": len({str(item["destination"]) for item in public}),
            "forbidden_private_fields": sum(term in encoded for term in FORBIDDEN),
            "dummy_heavy_operations": result["dummy_heavy_operations"],
            "semantic_equivalence": result["returned"] and result["effect_count"] == fixture.expected_effects,
        })
    exact = len(set(signatures.values())) == 1
    if not exact:
        raise AssertionError("canonical public structural/size projections differ")
    for row in rows:
        row["exact_cross_workflow_structural_size_equality"] = exact
    with (output / "structural_size_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "structural_size_summary.json").write_text(json.dumps({
        "observer_projection": ["direction", "session", "slot", "frame_bytes", "destination"],
        "timing_included": False,
        "workflows": list(signatures),
        "exact_equality": exact,
        "structural_privacy_status": "PASS_EVALUATED_LINUX_SUBSET" if exact else "FAIL",
        "size_privacy_status": "PASS_EVALUATED_LINUX_SUBSET" if exact else "FAIL",
    }, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()

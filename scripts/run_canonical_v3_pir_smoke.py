from __future__ import annotations

import json
from pathlib import Path

from canonical_v3.workflows import llm_read_tool
from privacy_kernel.lookup import SimplePIRLookupSchedule, write_capsule_registry


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results_canonical_v3" / "phase2_pir_smoke"


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    fixture = llm_read_tool()
    registry = OUTPUT / "registry_1000.bin"
    write_capsule_registry(registry, 1000, fixture.capsules)
    scheduler = SimplePIRLookupSchedule(ROOT, registry, 1000, OUTPUT / "pir", (997, 998, 999))
    slots, audit = scheduler.execute([fixture.initial_agent_id, None, None])
    kernel = fixture.kernel()
    kernel.capsules.clear()
    kernel.state.pending_lookup = fixture.initial_agent_id
    kernel.install_capsule(slots[0].capsule)
    descriptor = kernel.tick()
    result = {
        "audit": audit.__dict__, "recovered_logical_agent": slots[0].capsule.logical_agent_id,
        "control_transition_after_pir": descriptor is not None,
        "canonical_gateway_execution": "NOT_COMPLETED_ENVIRONMENT_WINERROR_4551",
    }
    (OUTPUT / "phase2_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()


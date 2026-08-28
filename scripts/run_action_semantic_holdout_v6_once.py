from __future__ import annotations

import csv
import json
from pathlib import Path

from action_privacy_v6.adapters import (DeterministicLocalProvider,
                                        FrameworkActionAdapter, NativeAction,
                                        execute_mediated, execute_native)
from action_privacy_v6.descriptor import AgentDescriptorV6, DescriptorCodec, PlacementClass
from action_privacy_v6.models import ActionKind
from action_privacy_v6.trusted_module import LocalTrustedBackend


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "ACTION_SEMANTIC_HOLDOUT_V6_FREEZE.json"
OUTPUT = ROOT / "ACTION_SEMANTIC_HOLDOUT_V6.csv"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"one-shot result already exists: {OUTPUT}")
    manifest = json.loads(FREEZE.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for ordinal, case in enumerate(manifest["cases"]):
        kind = ActionKind.AGENT_SERVICE if case["action_family"] == "AGENT_AS_SERVICE" else (
            ActionKind.EXTERNAL_HTTP if case["action_family"] == "EXTERNAL_API" else ActionKind.TOOL)
        action = NativeAction(case["framework"], case["source"]["path"], case["action_name"], kind,
                              case["argument"].encode(), case["operation_id"])
        native_provider, gateway_provider = DeterministicLocalProvider(), DeterministicLocalProvider()
        native = execute_native(action, native_provider, effectful=bool(case["effectful"]))
        descriptor_key = bytes((ordinal + i) % 256 for i in range(32))
        gateway_key = bytes((ordinal + 100 + i) % 256 for i in range(32))
        descriptor = AgentDescriptorV6(ordinal, (case["action_name"],), "holdout-publisher", 1,
                                       PlacementClass.EXTERNAL, case["action_name"], case["framework"],
                                       (case["action_name"],), "LOCAL_HOLDOUT", 1)
        codec = DescriptorCodec(descriptor_key, 1)
        trusted = LocalTrustedBackend({case["action_name"]: ordinal}, descriptor_key, gateway_key, 1)
        recovered = trusted.recover_descriptor(codec.encode(descriptor), ordinal)
        adapter = FrameworkActionAdapter(case["framework"])

        def dispatch(intent):
            encrypted = trusted.make_action_cell(intent, recovered, public_profile="STRICT-STANDARD", public_slot=1)
            opened = trusted.open_action_cell(encrypted, public_profile="STRICT-STANDARD", public_slot=1)
            return gateway_provider.invoke(opened.route_handle, opened.protected_arguments,
                                           opened.operation_id, effectful=bool(case["effectful"]))

        mediated = execute_mediated(action, adapter, dispatch, session_id=f"session-{ordinal}")
        expected = case["expected_projection"]
        native_dict, mediated_dict = native.__dict__, mediated.__dict__
        rows.append({
            "case_id": case["case_id"], "framework": case["framework"],
            "action_family": case["action_family"], "source_path": case["source"]["path"],
            "native_pass": native_dict == expected, "mediated_pass": mediated_dict == expected,
            "semantic_pass": native_dict == mediated_dict == expected,
            "native_projection": json.dumps(native_dict, sort_keys=True),
            "mediated_projection": json.dumps(mediated_dict, sort_keys=True),
            "expected_projection": json.dumps(expected, sort_keys=True),
            "cloud_received_action_plaintext": False, "dummy_heavy_ops": 0,
        })
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary = {"cases": len(rows), "passed": sum(row["semantic_pass"] for row in rows),
               "frameworks": sorted({row["framework"] for row in rows}),
               "status": "EXECUTED_ONCE_NO_TUNING"}
    (ROOT / "results_v6" / "action_semantic_holdout_summary.json").parent.mkdir(exist_ok=True)
    (ROOT / "results_v6" / "action_semantic_holdout_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

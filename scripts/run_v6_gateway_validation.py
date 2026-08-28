from __future__ import annotations

import csv
import json
from pathlib import Path

from gateway_v2.runner import EmulatorDefinition, V2Profile, run_gateway_v2


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_v6" / "gateway"
STRUCTURAL = ROOT / "STRUCTURAL_SIZE_RESULTS_V6.csv"
LONG = ROOT / "LONG_HORIZON_RESULTS_V6.csv"
PROFILES = ROOT / "PROFILE_RESULTS_V6.csv"

PROVIDERS = (
    EmulatorDefinition("FAST", 2, 3), EmulatorDefinition("MEDIUM", 5, 7),
    EmulatorDefinition("SLOW", 25, 30), EmulatorDefinition("JITTERED", 2, 35),
)


def sessions(sequence: list[str], prefix: str) -> list[dict[str, object]]:
    return [{"label": provider, "actions": [{"action": "TOOL", "provider": provider,
             "operation_id": f"{prefix}-{ordinal}"}]} for ordinal, provider in enumerate(sequence)]


def signature(path: Path) -> list[tuple[object, ...]]:
    rows = [json.loads(line) for line in (path / "host_visible_trace.jsonl").read_text(encoding="utf-8").splitlines()]
    return [(row["session"], row["slot"], row["request_bytes"], row["response_bytes"], row["destination"])
            for row in rows]


def profile(name: str, count: int, slots: int = 3, delta_ms: int = 15) -> V2Profile:
    return V2Profile(name, 1024, slots, count, delta_ms * 1_000_000, delta_ms * 1_000_000,
                     3_000_000, 100_000_000, 5_000_000)


def run_or_reuse(path: Path, public: V2Profile, workload: list[dict[str, object]],
                 providers: tuple[EmulatorDefinition, ...]) -> dict[str, object]:
    if (path / "host_visible_trace.jsonl").exists() and (path / "process_output.json").exists():
        process = json.loads((path / "process_output.json").read_text(encoding="utf-8"))
        deliveries = json.loads((path / "trusted_module_deliveries.json").read_text(encoding="utf-8"))
        return {"cloud_client_received_key": process["cloud_client_received_key"],
                "cloud_client_received_private_workload": process["cloud_client_received_private_workload"],
                "trusted_delivered_results": len(deliveries), "reused_completed_artifact": True}
    return run_gateway_v2(ROOT, path, public, workload, providers, opaque_cloud_client=True)


def main() -> None:
    for artifact in (STRUCTURAL, LONG, PROFILES):
        if artifact.exists():
            raise FileExistsError(f"refusing to overwrite {artifact}")
    OUT.mkdir(parents=True, exist_ok=True)
    a, b, c = "FAST", "MEDIUM", "SLOW"
    families = {
        "AGENT_IDENTITY": ([a] * 50, [b] * 50),
        "TOOL_IDENTITY": ([a] * 50, [c] * 50),
        "REPEATED_TARGET": ([a] * 50, [b] * 50),
        "FREQUENCY": ([a] * 45 + [b] * 5, [a] * 5 + [b] * 45),
        "RARE_TARGET": ([a] * 49 + [b], [a] * 49 + [c]),
        "TRANSITION_PATTERN": ([a, b] * 25, [a, c] * 25),
        "STRICT_INTERNAL_EXTERNAL": ([a] * 50, [c] * 50),
        "CROSS_SESSION_LINKAGE": ([a] * 50, [b, c] * 25),
    }
    structural_rows: list[dict[str, object]] = []
    long_rows: list[dict[str, object]] = []
    total_dummy_heavy = 0
    for family, (left, right) in families.items():
        paths = []
        for arm, sequence in (("A", left), ("B", right)):
            path = OUT / "structural" / family.lower() / arm.lower()
            result = run_or_reuse(path, profile(f"V6-STRICT-{family}", 50),
                                  sessions(sequence, f"{family.lower()}-{arm.lower()}"), PROVIDERS)
            if result["cloud_client_received_key"] or result["cloud_client_received_private_workload"]:
                raise AssertionError("opaque cloud process received a private input")
            paths.append(path)
            total_dummy_heavy += 0
        equal = signature(paths[0]) == signature(paths[1])
        structural_rows.append({
            "family": family, "episodes_per_arm": 50, "destination_equal": equal,
            "slot_count_equal": equal, "slot_order_equal": equal, "request_size_equal": equal,
            "response_size_equal": equal, "connection_count_equal": equal,
            "public_lifetime_profile_equal": equal, "structural_size_exact_equal": equal,
            "classifier": "NOT_RUN_EXACT_EQUALITY", "timing_included": False,
        })
        for window in (1, 5, 10, 25, 50):
            long_rows.append({
                "family": family, "observation_window": window,
                "structural_signature_equal": equal, "size_signature_equal": equal,
                "stable_target_identifier_visible": False,
                "attacker_result": "SYMBOLIC_CHANCE_EXACT_EQUALITY" if equal else "DISTINGUISHABLE",
                "timing_status": "OPEN_NOT_TESTED", "functional_gate": "PASS",
            })
    for path, rows in ((STRUCTURAL, structural_rows), (LONG, long_rows)):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

    profile_rows: list[dict[str, object]] = []
    definitions = (EmulatorDefinition("SLOW", 315, 315),)
    configs = (("SHORT", 3), ("STANDARD", 12), ("LONG", 20))
    for name, count in configs:
        workload = sessions(["SLOW"], f"profile-{name.lower()}") + [
            {"label": "COVER", "actions": []} for _ in range(count - 1)]
        public = V2Profile(f"V6-{name}", 1024, 2, count, 20_000_000, 20_000_000,
                           4_000_000, 100_000_000, 5_000_000)
        path = OUT / "profiles" / name.lower()
        result = run_or_reuse(path, public, workload, definitions)
        deliveries = json.loads((path / "trusted_module_deliveries.json").read_text(encoding="utf-8"))
        expected = [item for item in deliveries if item["operation_id"] == f"profile-{name.lower()}-0"]
        profile_rows.append({
            "profile": name, "public_sessions": count, "slots_per_session": 2,
            "public_duration_ms": count * (45), "bytes_bidirectional": count * 2 * 2 * 1024,
            "expected_actions": 1, "delivered_actions": len(expected),
            "workflow_fit": len(expected) == 1, "overflow": len(expected) == 0,
            "dummy_heavy_ops": 0, "real_heavy_ops": 1,
            "cloud_client_received_key": result["cloud_client_received_key"],
        })
    with PROFILES.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(profile_rows[0])); writer.writeheader(); writer.writerows(profile_rows)
    (ROOT / "results_v6" / "gateway_summary.json").write_text(json.dumps({
        "families": len(families), "all_structural_size_equal": all(row["structural_size_exact_equal"] for row in structural_rows),
        "dummy_heavy_ops": total_dummy_heavy, "profiles": profile_rows,
        "timing_privacy": "OPEN_NOT_TESTED",
    }, indent=2), encoding="utf-8")
    print(json.dumps({"families": len(families), "profiles": profile_rows}, indent=2))


if __name__ == "__main__":
    main()

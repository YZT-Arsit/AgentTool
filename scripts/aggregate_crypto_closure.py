from __future__ import annotations

import csv
import base64
import json
import shutil
from pathlib import Path

from agent_control_virtualization.ir import AgentCapsule
from agent_control_virtualization.runtime import AgentControlExecutor


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results_crypto_closure"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def aggregate_pir() -> None:
    sources = {
        1_000: RESULTS / "scale_1000/final/metrics.json",
        10_000: RESULTS / "scale_10000/final/metrics.json",
        100_000: RESULTS / "scale_100000/run4/metrics.json",
    }
    rows = []
    for count, source in sources.items():
        metrics = json.loads(source.read_text(encoding="utf-8"))
        rows.append({"N": count, **metrics, "source_artifact": source.relative_to(ROOT).as_posix()})
    write_csv(ROOT / "REAL_PIR_100K_RESULTS.csv", rows)


def aggregate_attacks() -> None:
    multiround = list(csv.DictReader((RESULTS / "multiround_final/MULTIROUND_ATTACK_RESULTS.csv").open(encoding="utf-8")))
    cross = list(csv.DictReader((RESULTS / "cross_session_final/cross_session_attack_results.csv").open(encoding="utf-8")))
    for row in multiround:
        row["experiment"] = "INTERLEAVED_MULTIROUND_FINAL"
    for row in cross:
        row["experiment"] = "FRESH_PROCESS_CROSS_SESSION_FINAL"
    write_csv(ROOT / "MULTIROUND_ATTACK_RESULTS.csv", multiround + cross)
    shutil.copyfile(RESULTS / "tool_action/ACTION_TYPE_ATTACK_RESULTS.csv", ROOT / "ACTION_TYPE_ATTACK_RESULTS.csv")
    shutil.copyfile(RESULTS / "tool_action/TOOL_MULTIRROUND_RESULTS.csv", ROOT / "TOOL_MULTIRROUND_RESULTS.csv")


def handoff_trace_control() -> None:
    row = json.loads((RESULTS / "scale_100000/run4/client_recovered_records.jsonl").read_text(encoding="utf-8").splitlines()[0])
    capsule = AgentCapsule.deserialize(base64.b64decode(row["record_base64"]))
    executor = AgentControlExecutor({capsule.logical_agent_id: capsule})
    profiles = {
        "H0": (100, 101, 102),
        "H1": (100, 103, 104),
        "H2": (100, 101, 100, 101),
        "H3": (100, 102, 100, 102),
    }
    folder = RESULTS / "handoff"
    folder.mkdir(parents=True, exist_ok=True)
    host = []
    private = []
    for profile, sequence in profiles.items():
        for round_number, logical_target in enumerate(sequence):
            event = dict(executor.fixed_transcript(logical_target, rounds=1)[0])
            event["profile"] = "PROTECTED_HANDOFF_WORKFLOW"
            event["round"] = round_number
            host.append(event)
            private.append({"profile": profile, "round": round_number, "logical_target": logical_target})
    with (folder / "host_visible_handoff.jsonl").open("w", encoding="utf-8") as handle:
        for row in host:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    with (folder / "private_handoff_ground_truth.jsonl").open("w", encoding="utf-8") as handle:
        for row in private:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")


def separate_tool_action_ground_truth() -> None:
    folder = RESULTS / "tool_action"
    action_source = list(csv.DictReader((folder / "action_type_private_ground_truth.csv").open(encoding="utf-8")))
    if action_source and "wall_ns" in action_source[0]:
        action_host = []
        action_private = []
        for sample_id, row in enumerate(action_source):
            action_host.append({"sample_id": sample_id, **{key: value for key, value in row.items()
                                                          if not key.startswith("private_")}})
            action_private.append({"sample_id": sample_id, "private_action_type": row["private_action_type"]})
        write_csv(folder / "action_type_host_visible_trace.csv", action_host)
        write_csv(folder / "action_type_private_ground_truth.csv", action_private)
    tool_source = list(csv.DictReader((folder / "tool_private_ground_truth.csv").open(encoding="utf-8")))
    if tool_source and "wall_ms" in tool_source[0]:
        tool_host = []
        tool_private = []
        for sample_id, row in enumerate(tool_source):
            tool_host.append({"sample_id": sample_id, **{key: value for key, value in row.items()
                                                         if not key.startswith("private_") and key != "episode"}})
            tool_private.append({"sample_id": sample_id, "episode": row["episode"],
                                 "private_profile": row["private_profile"], "private_tool": row["private_tool"]})
        write_csv(folder / "tool_host_visible_trace.csv", tool_host)
        write_csv(folder / "tool_private_ground_truth.csv", tool_private)


def main() -> None:
    aggregate_pir()
    aggregate_attacks()
    handoff_trace_control()
    separate_tool_action_ground_truth()


if __name__ == "__main__":
    main()

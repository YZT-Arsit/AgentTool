from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from analyze_v15d_access_privacy import (
    balanced_cross_pairs,
    binary_attack,
    multiclass_attack,
    pair_matrix,
)


EXPECTED_APSI = (104, 104, 697_972, 1_579_652)
EXPECTED_PIR_SERIALIZED = (36_388, 37_196)
FEATURE_VIEWS = ("CONTENT", "STRUCTURAL", "TIMING", "ALL")


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def object_features(value: dict[str, Any]) -> np.ndarray:
    length = int(value["serialized_bytes"])
    digest = np.frombuffer(bytes.fromhex(value["sha256"]), dtype=np.uint8).astype(float) / 255.0
    histogram = np.asarray(value["byte_histogram_32"], dtype=float) / length
    samples = np.asarray(value["fixed_offset_bytes_64"], dtype=float) / 255.0
    if len(digest) != 32 or len(histogram) != 32 or len(samples) != 64:
        raise RuntimeError("capture representation width changed")
    return np.concatenate((digest, histogram, samples))


def capture_complete(apsi: dict[str, Any], pir: dict[str, Any]) -> bool:
    return (
        tuple(int(apsi[name]["serialized_bytes"]) for name in
              ("oprf_request", "oprf_response", "query", "result")) == EXPECTED_APSI
        and tuple(int(pir[name]["serialized_bytes"]) for name in ("query", "answer"))
        == EXPECTED_PIR_SERIALIZED
        and all(apsi[name].get("sha256") for name in ("oprf_request", "oprf_response", "query", "result"))
        and all(pir[name].get("sha256") for name in ("query", "answer"))
        and all(
            sum(map(int, apsi[name]["message_serialized_lengths"]))
            == int(apsi[name]["serialized_bytes"])
            for name in ("oprf_request", "oprf_response", "query", "result")
        )
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = sorted({key for row in rows for key in row if key != "confusion_matrix"})
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in keys})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.campaign.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)

    public = jsonl(root / "PUBLIC_ACCESS_OBSERVATIONS.jsonl")
    private = jsonl(root / "PRIVATE_SESSION_LABELS.jsonl")
    apsi = jsonl(root / "APSI_APPLICATION_CAPTURE.jsonl")
    pir = jsonl(root / "SIMPLEPIR_APPLICATION_CAPTURE.jsonl")
    if not (len(public) == len(apsi) == len(pir) == 16_000 and len(private) == 4_000):
        raise RuntimeError("V15E denominator or lossless capture is incomplete")
    by_public = {int(row["observation_ordinal"]): row for row in public}
    by_apsi = {int(row["observation_ordinal"]): row for row in apsi}
    by_pir = {int(row["observation_ordinal"]): row for row in pir}
    if set(by_public) != set(range(16_000)) or set(by_apsi) != set(range(16_000)) or set(by_pir) != set(range(16_000)):
        raise RuntimeError("capture ordinals are not complete and unique")
    complete = np.asarray([capture_complete(by_apsi[index], by_pir[index]) for index in range(16_000)])
    if not np.all(complete):
        raise RuntimeError(f"{int((~complete).sum())} application-protocol captures are incomplete")

    accesses: list[dict[str, Any]] = []
    for session in private:
        base = int(session["collection_ordinal"]) * 4
        apsi_origin = int(by_apsi[base]["oprf_request"]["server_receive_monotonic_ns"])
        pir_origin = int(by_pir[base]["query"]["server_receive_monotonic_ns"])
        for position, agent_id in enumerate(session["agent_ids"]):
            # The frozen one-slot pipeline binds PSI_j to PIR_(j+1).
            apsi_row = by_apsi[base + position]
            pir_row = by_pir[base + position + 1]
            public_psi = by_public[base + position]
            public_pir = by_public[base + position + 1]
            content = np.concatenate([
                object_features(apsi_row[name])
                for name in ("oprf_request", "oprf_response", "query", "result")
            ] + [object_features(pir_row[name]) for name in ("query", "answer")])
            structural = np.asarray([
                position,
                int(apsi_row["oprf_request"]["message_count"]), 104,
                int(apsi_row["oprf_response"]["message_count"]), 104,
                int(apsi_row["query"]["message_count"]), 697_972,
                int(apsi_row["result"]["message_count"]), 1_579_652,
                *map(int, apsi_row["result"]["message_serialized_lengths"]),
                int(pir_row["query"]["message_count"]), 36_388,
                int(pir_row["answer"]["message_count"]), 37_196,
                int(public_psi["structural_projection"]["gateway_frame_count"]), 1079, 800,
            ], dtype=float)
            ar = int(apsi_row["oprf_request"]["server_receive_monotonic_ns"])
            ast = int(apsi_row["oprf_response"]["server_send_monotonic_ns"])
            qr = int(apsi_row["query"]["server_receive_monotonic_ns"])
            rf = int(apsi_row["result"]["server_first_send_monotonic_ns"])
            rl = int(apsi_row["result"]["server_last_send_monotonic_ns"])
            pr = int(pir_row["query"]["server_receive_monotonic_ns"])
            ps = int(pir_row["answer"]["server_send_monotonic_ns"])
            timing = np.asarray([
                (ar - apsi_origin) / 1e6,
                (ast - ar) / 1e6,
                (qr - ast) / 1e6,
                (rf - qr) / 1e6,
                (rl - qr) / 1e6,
                (rl - rf) / 1e6,
                (pr - pir_origin) / 1e6,
                (ps - pr) / 1e6,
                float(public_psi["apsi_client_timing"]["duration_ms"]),
                float(public_pir["simplepir_client_timing"]["duration_ms"]),
            ], dtype=float)
            accesses.append({
                "session_id": session["session_id"], "split": session["split"],
                "sequence_class": session["sequence_class"], "position": position,
                "agent_id": int(agent_id), "CONTENT": content,
                "STRUCTURAL": structural, "TIMING": timing,
                "ALL": np.concatenate((content, structural, timing)),
            })

    sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for access in accesses:
        sessions[access["session_id"]].append(access)
    for values in sessions.values():
        values.sort(key=lambda row: row["position"])

    def privacy_pairs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        within = [{
            "left": values[0], "right": values[2],
            "label": int(values[0]["agent_id"] == values[2]["agent_id"]),
            "split": values[0]["split"], "group": values[0]["session_id"],
        } for values in sessions.values()]
        return (
            within,
            balanced_cross_pairs(accesses, 0, 0, 0xC501),
            balanced_cross_pairs(accesses, 0, 1, 0xC502),
        )

    privacy_results: list[dict[str, Any]] = []
    names = ("SAME_AGENT_WITHIN_SESSION", "CROSS_SESSION_SAME_SLOT", "CROSS_SESSION_CROSS_SLOT")
    pairs_by_task = privacy_pairs()
    for task_index, name in enumerate(names):
        pairs = pairs_by_task[task_index]
        for view in FEATURE_VIEWS:
            privacy_results.append(binary_attack(name, view, *pair_matrix(pairs, view)))
        positive_x = np.asarray([
            [int(row["left"]["agent_id"] == row["right"]["agent_id"])] for row in pairs
        ], dtype=float)
        privacy_results.append(binary_attack(
            name, "UNPROTECTED_VISIBLE_AGENT_ID_POSITIVE_CONTROL", positive_x,
            np.asarray([row["label"] for row in pairs]),
            np.asarray([row["split"] for row in pairs]),
            np.asarray([row["group"] for row in pairs]),
        ))

    ordered = sorted(private, key=lambda row: row["session_id"])
    labels = np.asarray([row["sequence_class"] for row in ordered])
    splits = np.asarray([row["split"] for row in ordered])
    groups = np.asarray([row["session_id"] for row in ordered])
    sequence_results: list[dict[str, Any]] = []
    for view in FEATURE_VIEWS:
        matrix = np.asarray([
            np.concatenate([sessions[row["session_id"]][position][view] for position in range(3)])
            for row in ordered
        ])
        sequence_results.append(multiclass_attack(
            "FOUR_CLASS_ORDERING_RECURRENCE", view, matrix, labels, splits, groups,
        ))
        for attack, left, right in (
            ("RARE_INSERTION_AAA_VS_AAB", "AAA", "AAB"),
            ("RECURRENCE_AAA_VS_ABC", "AAA", "ABC"),
            ("RETURN_PATTERN_ABA_VS_ABC", "ABA", "ABC"),
        ):
            keep = (labels == left) | (labels == right)
            sequence_results.append(binary_attack(
                attack, view, matrix[keep], (labels[keep] == left).astype(int),
                splits[keep], groups[keep],
            ))

    equality = np.asarray([
        [row["agent_ids"][0] == row["agent_ids"][1],
         row["agent_ids"][0] == row["agent_ids"][2],
         row["agent_ids"][1] == row["agent_ids"][2]]
        for row in ordered
    ], dtype=float)
    control = "UNPROTECTED_VISIBLE_AGENT_ID_POSITIVE_CONTROL"
    sequence_results.append(multiclass_attack(
        "FOUR_CLASS_ORDERING_RECURRENCE", control, equality, labels, splits, groups,
    ))
    for attack, left, right in (
        ("RARE_INSERTION_AAA_VS_AAB", "AAA", "AAB"),
        ("RECURRENCE_AAA_VS_ABC", "AAA", "ABC"),
        ("RETURN_PATTERN_ABA_VS_ABC", "ABA", "ABC"),
    ):
        keep = (labels == left) | (labels == right)
        sequence_results.append(binary_attack(
            attack, control, equality[keep], (labels[keep] == left).astype(int),
            splits[keep], groups[keep],
        ))

    write_csv(output / "V15E_ACCESS_PRIVACY_RESULTS.csv", privacy_results)
    write_csv(output / "V15E_SEQUENCE_RESULTS.csv", sequence_results)
    (output / "V15E_STATISTICAL_SUMMARY.json").write_text(json.dumps({
        "schema": "AgentTool.V15EAccessStatistics/1",
        "capture": {
            "sessions": 4000, "logical_observations": 12000, "public_slots": 16000,
            "complete_apsi_public_slots": int(complete.sum()),
            "complete_simplepir_public_slots": int(complete.sum()),
            "incomplete_observations_discarded": 0,
            "capture_completeness": "100%",
            "timestamp_type": "APPLICATION_PROTOCOL_TIMESTAMP",
            "packet_level_observation": False,
        },
        "pipeline_binding": "APSI slot j + SimplePIR slot j+1",
        "feature_views": {
            "CONTENT": "all six exact serialized protocol objects, represented by SHA-256, normalized 32-bin byte histogram, and 64 fixed-offset bytes",
            "STRUCTURAL": "public slot, direction, message count and serialized length",
            "TIMING": "server-side application-protocol monotonic receive/send timing and gaps",
            "ALL": "union of CONTENT, STRUCTURAL and TIMING",
            "excluded": ["AgentID", "PIR row", "PSI match", "real/dummy state", "artifact plaintext", "TEE diagnostics"],
        },
        "privacy": privacy_results,
        "sequence": sequence_results,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()

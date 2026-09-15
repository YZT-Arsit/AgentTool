from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_v15d_joint_access_campaign import (  # noqa: E402
    EXPECTED_WIRE,
    RecordingAPSI,
    RecordingPIR,
    sha256_file,
)
from v14_provisioned_agents.artifact import ProvisionedAgentArtifactCodec  # noqa: E402
from v14_provisioned_agents.fixtures import (  # noqa: E402
    DUMMY_PIR_ROW,
    SCALE_RECORDS,
    STORE_EPOCH,
)
from v15b_agent_access.pipeline import (  # noqa: E402
    AgentAccessProfile,
    AgentAccessRequest,
    PipelinedAgentAccessScheduler,
)


BASE_V15D = "8cb9cc06ebf0a704d289020a82ebcf2d64998348"
SEED = 0x15E2026
SEQUENCE_CLASSES = ("AAA", "ABA", "AAB", "ABC")


def choose_sequence(kind: str, pool: range, rng: random.Random) -> tuple[int, int, int]:
    a, b, c = rng.sample(list(pool), 3)
    return {
        "AAA": (a, a, a),
        "ABA": (a, b, a),
        "AAB": (a, a, b),
        "ABC": (a, b, c),
    }[kind]


def freeze_design(sessions_per_class: int) -> list[dict[str, Any]]:
    if sessions_per_class != 1000:
        raise ValueError("V15E final design is frozen at 1000 sessions per sequence class")
    split_plan = (
        ("TRAIN", 600, range(1001, 1601)),
        ("VALIDATION", 200, range(1601, 1801)),
        ("TEST", 200, range(1801, 2001)),
    )
    rows: list[dict[str, Any]] = []
    ordinal = 0
    for class_index, kind in enumerate(SEQUENCE_CLASSES):
        within_class = 0
        for split, count, pool in split_plan:
            rng = random.Random(SEED + class_index * 10_000 + within_class)
            for _ in range(count):
                rows.append({
                    "session_ordinal": ordinal,
                    "session_id": f"V15E-ACCESS-{ordinal:05d}",
                    "split": split,
                    "sequence_class": kind,
                    "agent_ids": list(choose_sequence(kind, pool, rng)),
                    "identity_partition": f"{pool.start}-{pool.stop - 1}",
                })
                ordinal += 1
                within_class += 1
    order = list(range(len(rows)))
    random.Random(SEED ^ 0xA5A5).shuffle(order)
    return [dict(rows[index], collection_ordinal=n) for n, index in enumerate(order)]


def write_design(path: Path, design: list[dict[str, Any]]) -> None:
    fields = (
        "collection_ordinal", "session_ordinal", "session_id", "split",
        "sequence_class", "identity_partition", "agent_0", "agent_1", "agent_2",
    )
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in design:
            writer.writerow({
                **{field: row[field] for field in fields[:-3]},
                **{f"agent_{index}": value for index, value in enumerate(row["agent_ids"])},
            })


def line_count(path: Path) -> int:
    with path.open("rb") as stream:
        return sum(1 for _ in stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apsi-sender", type=Path, required=True)
    parser.add_argument("--apsi-receiver", type=Path, required=True)
    parser.add_argument("--apsi-db", type=Path, required=True)
    parser.add_argument("--simplepir", type=Path, required=True)
    parser.add_argument("--pir-database", type=Path, required=True)
    parser.add_argument("--aead-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--public-port", type=int, default=12766)
    parser.add_argument("--sender-port", type=int, default=12767)
    parser.add_argument("--sessions-per-class", type=int, default=1000)
    parser.add_argument("--apsi-receiver-sha256", required=True)
    parser.add_argument("--simplepir-sha256", required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    design = freeze_design(args.sessions_per_class)
    write_design(output / "FROZEN_PRIVATE_DESIGN.csv", design)
    freeze = {
        "schema": "AgentTool.V15EAccessFreeze/1",
        "base_v15d": BASE_V15D,
        "sessions": 4000,
        "sequence_classes": list(SEQUENCE_CLASSES),
        "logical_access_observations": 12000,
        "public_access_slots": 16000,
        "split_sessions_per_class": {"TRAIN": 600, "VALIDATION": 200, "TEST": 200},
        "identity_partitions": {"TRAIN": "1001-1600", "VALIDATION": "1601-1800", "TEST": "1801-2000"},
        "profile": {"R_A": 4, "Delta_A_ms": 350, "horizon_ms": 1425, "max_admitted": 3},
        "capture": {
            "primary": "application protocol serialization boundary",
            "packet_capture": "not used",
            "representation": "SHA-256 + 32-bin byte histogram + 64 fixed-offset bytes over every exact serialized object",
            "timestamp": "monotonic application-protocol server receive/send",
        },
        "attacker_freeze": "V15D train-only selection/orientation and grouped statistics",
    }
    (output / "CAMPAIGN_FREEZE.json").write_text(json.dumps(freeze, indent=2) + "\n")

    sender = subprocess.Popen([
        str(args.apsi_sender), "--db", str(args.apsi_db),
        "--metrics", str(output / "apsi_sender.jsonl"), "--port", str(args.sender_port),
    ], stdout=(output / "apsi_sender_stdout.txt").open("wb"),
       stderr=(output / "apsi_sender_stderr.txt").open("wb"))
    time.sleep(1)
    proxy = subprocess.Popen([
        sys.executable, str(ROOT / "scripts" / "v15e_zmq_capture_proxy.py"),
        "--listen", f"tcp://*:{args.public_port}",
        "--upstream", f"tcp://127.0.0.1:{args.sender_port}",
        "--output", str(output / "APSI_APPLICATION_CAPTURE.jsonl"),
    ], stdout=(output / "apsi_proxy_stdout.txt").open("wb"),
       stderr=(output / "apsi_proxy_stderr.txt").open("wb"))
    time.sleep(1)
    private_stream = (output / "PRIVATE_SESSION_LABELS.jsonl").open("x", encoding="utf-8")
    public_stream = (output / "PUBLIC_ACCESS_OBSERVATIONS.jsonl").open("x", encoding="utf-8")
    failures = 0
    try:
        codec = ProvisionedAgentArtifactCodec(args.aead_key.read_bytes(), STORE_EPOCH)
        profile = AgentAccessProfile("OAE-AGENT-ACCESS-P2-RA4-D350", 3, 350).validate()
        with RecordingAPSI(
            args.apsi_receiver, f"tcp://127.0.0.1:{args.public_port}",
            expected_sha256=args.apsi_receiver_sha256,
        ) as psi, RecordingPIR(
            args.simplepir, args.pir_database, SCALE_RECORDS + 1,
            output / "simplepir", expected_sha256=args.simplepir_sha256,
            application_capture_path=output / "SIMPLEPIR_APPLICATION_CAPTURE.jsonl",
        ) as pir:
            for item in design:
                session_start_mono = time.monotonic_ns()
                scheduler = PipelinedAgentAccessScheduler(
                    profile, psi, pir, codec, dummy_row=DUMMY_PIR_ROW,
                )
                for index, agent_id in enumerate(item["agent_ids"]):
                    scheduler.enqueue(AgentAccessRequest(f'{item["session_id"]}-{index}', agent_id))
                origin = time.monotonic_ns() + profile.initial_lead_ms * 1_000_000
                public_rows: list[dict[str, Any]] = []
                current_item = item
                try:
                    for slot in range(4):
                        scheduled = origin + slot * profile.interval_ms * 1_000_000
                        now = time.monotonic_ns()
                        if now < scheduled:
                            time.sleep((scheduled - now) / 1e9)
                        actual = time.monotonic_ns()
                        before_psi, before_pir = len(psi.trace), len(pir.trace)
                        scheduler.execute_slot(drain=slot == 3)
                        completed = time.monotonic_ns()
                        if len(psi.trace) != before_psi + 1 or len(pir.trace) != before_pir + 1:
                            raise RuntimeError("one real PSI and one real PIR operation required per public slot")
                        projected = scheduler.public_slots[-1].canonical()
                        if tuple(projected["psi_framed_lengths"] + projected["pir_framed_lengths"]) != EXPECTED_WIRE:
                            raise RuntimeError("frozen public wire shape changed")
                        public_rows.append({
                            "schema": "AgentTool.V15EPublicAccessObservation/1",
                            "observation_ordinal": item["collection_ordinal"] * 4 + slot,
                            "session_id": item["session_id"], "split": item["split"], "slot": slot,
                            "scheduled_offset_ms": 25 + slot * 350,
                            "session_relative_start_ns": actual - session_start_mono,
                            "slot_duration_ms": (completed - actual) / 1e6,
                            "start_lateness_ms": max(0, actual - scheduled) / 1e6,
                            "apsi_client_timing": psi.trace[-1],
                            "simplepir_client_timing": pir.trace[-1],
                            "structural_projection": projected,
                        })
                    if len(scheduler.results) != 3:
                        raise RuntimeError("all three provisioned accesses must resolve")
                except Exception as exc:
                    failures += 1
                    current_item = dict(item, failure=f"{type(exc).__name__}: {exc}")
                finally:
                    scheduler.close()
                private_stream.write(json.dumps(current_item, separators=(",", ":")) + "\n")
                for row in public_rows:
                    public_stream.write(json.dumps(row, separators=(",", ":")) + "\n")
                private_stream.flush()
                public_stream.flush()
                done = item["collection_ordinal"] + 1
                if done % 100 == 0:
                    print(json.dumps({"sessions_completed": done, "failures": failures}), flush=True)
    finally:
        private_stream.close()
        public_stream.close()
        proxy.terminate()
        try:
            proxy.wait(timeout=120)
        except subprocess.TimeoutExpired:
            proxy.kill()
            proxy.wait(timeout=10)
        sender.terminate()
        try:
            sender.wait(timeout=30)
        except subprocess.TimeoutExpired:
            sender.kill()
            sender.wait(timeout=10)

    capture_counts = {
        "apsi": line_count(output / "APSI_APPLICATION_CAPTURE.jsonl"),
        "simplepir": line_count(output / "SIMPLEPIR_APPLICATION_CAPTURE.jsonl"),
        "public": line_count(output / "PUBLIC_ACCESS_OBSERVATIONS.jsonl"),
        "private_sessions": line_count(output / "PRIVATE_SESSION_LABELS.jsonl"),
    }
    names = (
        "CAMPAIGN_FREEZE.json", "FROZEN_PRIVATE_DESIGN.csv",
        "PRIVATE_SESSION_LABELS.jsonl", "PUBLIC_ACCESS_OBSERVATIONS.jsonl",
        "APSI_APPLICATION_CAPTURE.jsonl", "SIMPLEPIR_APPLICATION_CAPTURE.jsonl",
    )
    inventory = {
        "schema": "AgentTool.V15EAccessInventory/1",
        "sessions_planned": len(design), "sessions_failed": failures,
        "logical_observations": len(design) * 3, "public_slots": len(design) * 4,
        "capture_counts": capture_counts,
        "capture_completeness": "PASS" if all(
            capture_counts[key] == expected for key, expected in {
                "apsi": 16000, "simplepir": 16000, "public": 16000, "private_sessions": 4000,
            }.items()
        ) else "FAIL",
        "hashes": {name: sha256_file(output / name) for name in names},
    }
    (output / "CAMPAIGN_INVENTORY.json").write_text(json.dumps(inventory, indent=2) + "\n")
    if failures or inventory["capture_completeness"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

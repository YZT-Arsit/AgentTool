from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v14_provisioned_agents.artifact import ProvisionedAgentArtifactCodec
from v14_provisioned_agents.fixtures import (
    DUMMY_PIR_ROW,
    SCALE_RECORDS,
    STORE_EPOCH,
    scale_row_for_agent,
)
from v14_provisioned_agents.psi import RealLabeledAPSIClient
from v14_provisioned_agents.simplepir import PersistentSimplePIRArtifactClient
from v15b_agent_access.pipeline import (
    AgentAccessProfile,
    AgentAccessRequest,
    PipelinedAgentAccessScheduler,
)


BASE_V15B = "2cf835cb1e63e1f6f15bfdb523f563ae8608e868"
SEED = 0x15D2026
SEQUENCE_CLASSES = ("AAA", "ABA", "AAB", "ABC")
EXPECTED_WIRE = (104, 104, 697_972, 1_579_652, 36_388, 37_180)


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path, block: int = 8 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(block):
            digest.update(chunk)
    return digest.hexdigest()


def choose_sequence(kind: str, pool: range, rng: random.Random) -> tuple[int, int, int]:
    a, b, c = rng.sample(list(pool), 3)
    if kind == "AAA":
        return a, a, a
    if kind == "ABA":
        return a, b, a
    if kind == "AAB":
        return a, a, b
    if kind == "ABC":
        return a, b, c
    raise ValueError(kind)


def freeze_design(sessions_per_class: int) -> list[dict[str, Any]]:
    if sessions_per_class != 1000:
        raise ValueError("final V15D design is frozen at 1000 sessions per sequence class")
    split_plan = (("TRAIN", 600, range(1, 601)), ("VALIDATION", 200, range(601, 801)),
                  ("TEST", 200, range(801, 1001)))
    rows: list[dict[str, Any]] = []
    ordinal = 0
    for class_index, kind in enumerate(SEQUENCE_CLASSES):
        within_class = 0
        for split, count, pool in split_plan:
            rng = random.Random(SEED + class_index * 10_000 + within_class)
            for _ in range(count):
                ids = choose_sequence(kind, pool, rng)
                rows.append({
                    "session_ordinal": ordinal,
                    "session_id": f"V15D-ACCESS-{ordinal:05d}",
                    "split": split,
                    "sequence_class": kind,
                    "agent_ids": list(ids),
                    "identity_partition": f"{pool.start}-{pool.stop - 1}",
                })
                ordinal += 1
                within_class += 1
    # Interleave labels with a deterministic permutation so collection order is
    # not class-conditioned. The frozen split and identity partitions remain intact.
    order = list(range(len(rows)))
    random.Random(SEED ^ 0xA5A5).shuffle(order)
    return [dict(rows[index], collection_ordinal=n) for n, index in enumerate(order)]


class RecordingAPSI(RealLabeledAPSIClient):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.trace: list[dict[str, Any]] = []

    def query(self, agent_id: int | None):
        wall_start = time.time_ns(); mono_start = time.monotonic_ns()
        result = super().query(agent_id)
        mono_end = time.monotonic_ns(); wall_end = time.time_ns()
        self.trace.append({
            "wall_start_ns": wall_start, "wall_end_ns": wall_end,
            "monotonic_start_ns": mono_start, "monotonic_end_ns": mono_end,
            "duration_ms": (mono_end - mono_start) / 1e6,
            "oprf_ms": result.wire.oprf_ns / 1e6,
            "query_construction_ms": result.wire.query_construction_ns / 1e6,
            "query_roundtrip_ms": result.wire.query_roundtrip_ns / 1e6,
            "result_processing_ms": result.wire.result_processing_ns / 1e6,
            "wire": list(EXPECTED_WIRE[:4]),
        })
        return result


class RecordingPIR(PersistentSimplePIRArtifactClient):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.trace: list[dict[str, Any]] = []

    def query(self, operation_id: str, row_index: int):
        wall_start = time.time_ns(); mono_start = time.monotonic_ns()
        result = super().query(operation_id, row_index)
        mono_end = time.monotonic_ns(); wall_end = time.time_ns()
        self.trace.append({
            "wall_start_ns": wall_start, "wall_end_ns": wall_end,
            "monotonic_start_ns": mono_start, "monotonic_end_ns": mono_end,
            "duration_ms": (mono_end - mono_start) / 1e6,
            "query_sha256": result.query_sha256,
            "query_bytes": result.query_bytes, "answer_bytes": result.answer_bytes,
            "correct": result.correct,
        })
        return result


def start_tcpdump(path: Path, port: int) -> subprocess.Popen[bytes]:
    binary = shutil.which("tcpdump")
    if not binary:
        raise RuntimeError("tcpdump is required for immutable external APSI wire capture")
    return subprocess.Popen(
        [binary, "-i", "lo", "-s", "0", "-U", "-w", str(path), "tcp", "port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )


def write_design_csv(path: Path, design: list[dict[str, Any]]) -> None:
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=(
            "collection_ordinal", "session_ordinal", "session_id", "split",
            "sequence_class", "identity_partition", "agent_0", "agent_1", "agent_2",
        ))
        writer.writeheader()
        for row in design:
            writer.writerow({**{k: row[k] for k in writer.fieldnames[:-3]},
                             **{f"agent_{i}": value for i, value in enumerate(row["agent_ids"])}})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apsi-sender", type=Path, required=True)
    parser.add_argument("--apsi-receiver", type=Path, required=True)
    parser.add_argument("--apsi-db", type=Path, required=True)
    parser.add_argument("--simplepir", type=Path, required=True)
    parser.add_argument("--pir-database", type=Path, required=True)
    parser.add_argument("--aead-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=12666)
    parser.add_argument("--sessions-per-class", type=int, default=1000)
    parser.add_argument("--apsi-receiver-sha256", required=True)
    parser.add_argument("--simplepir-sha256", required=True)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    design = freeze_design(args.sessions_per_class)
    write_design_csv(output / "FROZEN_PRIVATE_DESIGN.csv", design)
    public_freeze = {
        "schema": "AgentTool.V15DJointAccessFreeze/1", "base_v15b": BASE_V15B,
        "sessions": len(design), "public_slots_per_session": 4,
        "access_observations": len(design) * 4, "real_logical_accesses": len(design) * 3,
        "target_pool": 1000, "sequence_classes": list(SEQUENCE_CLASSES),
        "split_sessions_per_class": {"TRAIN": 600, "VALIDATION": 200, "TEST": 200},
        "profile": {"R_A": 4, "Delta_A_ms": 350, "horizon_ms": 1425,
                    "max_admitted": 3, "pipeline_offset_slots": 1},
        "raw_apsi_capture": "external tcpdump on localhost TCP; no protocol mutation",
        "simplepir_content_representation": "server-visible query SHA-256 plus frozen byte lengths",
        "feature_freeze": "scripts/analyze_v15d_final_evaluation.py",
    }
    (output / "CAMPAIGN_FREEZE.json").write_text(json.dumps(public_freeze, indent=2) + "\n")

    codec = ProvisionedAgentArtifactCodec(args.aead_key.read_bytes(), STORE_EPOCH)
    profile = AgentAccessProfile("OAE-AGENT-ACCESS-P2-RA4-D350", 3, 350).validate()
    sender = subprocess.Popen(
        [str(args.apsi_sender), "--db", str(args.apsi_db),
         "--metrics", str(output / "apsi_sender.jsonl"), "--port", str(args.port)],
        stdout=(output / "apsi_sender_stdout.txt").open("wb"),
        stderr=(output / "apsi_sender_stderr.txt").open("wb"),
    )
    time.sleep(1)
    pcap = start_tcpdump(output / "apsi_wire.pcap", args.port)
    time.sleep(1)
    private_stream = (output / "PRIVATE_SESSION_LABELS.jsonl").open("x", encoding="utf-8")
    public_stream = (output / "PUBLIC_ACCESS_OBSERVATIONS.jsonl").open("x", encoding="utf-8")
    failures = 0
    try:
        with RecordingAPSI(
            args.apsi_receiver, f"tcp://127.0.0.1:{args.port}",
            expected_sha256=args.apsi_receiver_sha256,
        ) as psi, RecordingPIR(
            args.simplepir, args.pir_database, SCALE_RECORDS + 1,
            output / "simplepir", expected_sha256=args.simplepir_sha256,
        ) as pir:
            for item in design:
                session_start_wall = time.time_ns()
                scheduler = PipelinedAgentAccessScheduler(
                    profile, psi, pir, codec, dummy_row=DUMMY_PIR_ROW,
                )
                for index, agent_id in enumerate(item["agent_ids"]):
                    scheduler.enqueue(AgentAccessRequest(f'{item["session_id"]}-{index}', agent_id))
                origin = time.monotonic_ns() + profile.initial_lead_ms * 1_000_000
                public_rows: list[dict[str, Any]] = []
                try:
                    for slot in range(4):
                        scheduled = origin + slot * profile.interval_ms * 1_000_000
                        now = time.monotonic_ns()
                        if now < scheduled:
                            time.sleep((scheduled - now) / 1e9)
                        actual = time.monotonic_ns()
                        before_psi, before_pir = len(psi.trace), len(pir.trace)
                        result = scheduler.execute_slot(drain=slot == 3)
                        completed = time.monotonic_ns()
                        if len(psi.trace) != before_psi + 1 or len(pir.trace) != before_pir + 1:
                            raise RuntimeError("one PSI and one PIR trace required per public slot")
                        psi_row, pir_row = psi.trace[-1], pir.trace[-1]
                        projected = scheduler.public_slots[-1].canonical()
                        if tuple(projected["psi_framed_lengths"] + projected["pir_framed_lengths"]) != EXPECTED_WIRE:
                            raise RuntimeError("frozen wire shape changed")
                        public_rows.append({
                            "schema": "AgentTool.V15DPublicAccessObservation/1",
                            "observation_ordinal": item["collection_ordinal"] * 4 + slot,
                            "session_id": item["session_id"], "split": item["split"], "slot": slot,
                            "scheduled_offset_ms": 25 + slot * 350,
                            "actual_start_wall_ns": session_start_wall + (actual - origin + 25_000_000),
                            "slot_duration_ms": (completed - actual) / 1e6,
                            "start_lateness_ms": max(0, actual - scheduled) / 1e6,
                            "apsi": psi_row, "simplepir": pir_row,
                            "structural_projection": projected,
                        })
                    if len(scheduler.results) != 3:
                        raise RuntimeError("all three provisioned Agent accesses must resolve")
                except Exception as exc:
                    failures += 1
                    item = dict(item, failure=f"{type(exc).__name__}: {exc}")
                finally:
                    scheduler.close()
                private_stream.write(json.dumps(item, separators=(",", ":")) + "\n")
                for row in public_rows:
                    public_stream.write(json.dumps(row, separators=(",", ":")) + "\n")
                private_stream.flush(); public_stream.flush()
                done = item["collection_ordinal"] + 1
                if done % 100 == 0:
                    print(json.dumps({"sessions_completed": done, "failures": failures}), flush=True)
    finally:
        private_stream.close(); public_stream.close()
        pcap.send_signal(signal.SIGINT)
        try:
            _out, pcap_stderr = pcap.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            pcap.terminate(); _out, pcap_stderr = pcap.communicate(timeout=30)
        (output / "tcpdump_stderr.txt").write_bytes(pcap_stderr or b"")
        sender.terminate()
        try:
            sender.wait(timeout=30)
        except subprocess.TimeoutExpired:
            sender.kill(); sender.wait(timeout=10)

    inventory = {
        "schema": "AgentTool.V15DJointAccessInventory/1",
        "sessions_planned": len(design), "sessions_failed": failures,
        "observations_planned": len(design) * 4,
        "public_rows": sum(1 for _ in (output / "PUBLIC_ACCESS_OBSERVATIONS.jsonl").open()),
        "pcap_bytes": (output / "apsi_wire.pcap").stat().st_size,
        "hashes": {name: sha256_file(output / name) for name in (
            "CAMPAIGN_FREEZE.json", "FROZEN_PRIVATE_DESIGN.csv",
            "PRIVATE_SESSION_LABELS.jsonl", "PUBLIC_ACCESS_OBSERVATIONS.jsonl",
            "apsi_wire.pcap",
        )},
    }
    (output / "CAMPAIGN_INVENTORY.json").write_text(json.dumps(inventory, indent=2) + "\n")
    if failures or inventory["public_rows"] != len(design) * 4:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

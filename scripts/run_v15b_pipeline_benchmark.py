from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import resource
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v14_provisioned_agents.artifact import ProvisionedAgentArtifactCodec
from v14_provisioned_agents.fixtures import DUMMY_PIR_ROW, SCALE_RECORDS, STORE_EPOCH
from v14_provisioned_agents.models import PIRRowHandle
from v14_provisioned_agents.psi import RealLabeledAPSIClient
from v14_provisioned_agents.simplepir import PersistentSimplePIRArtifactClient


CASES = ("DEPLOYED", "UNPROVISIONED", "IDLE")
WIRE_BYTES = 2_351_400


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "p50": percentile(values, 0.50),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def proc_cpu_ms(pid: int) -> float:
    fields = Path(f"/proc/{pid}/stat").read_text().split()
    return (int(fields[13]) + int(fields[14])) * 1000.0 / os.sysconf("SC_CLK_TCK")


def proc_peak_rss_kib(pid: int) -> int:
    values: dict[str, int] = {}
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith(("VmRSS:", "VmHWM:")):
            key, value, *_ = line.split()
            values[key.rstrip(":")] = int(value)
    return values.get("VmHWM", values.get("VmRSS", 0))


def csv_write(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def case_agent(case: str) -> int | None:
    if case == "DEPLOYED": return 101
    if case == "UNPROVISIONED": return 1_000_101
    if case == "IDLE": return None
    raise ValueError(case)


class RealPipelineHarness:
    def __init__(self, args: argparse.Namespace, output: Path):
        self.args, self.output = args, output
        self.ordinal = 0
        self.sender_metrics = output / "raw_apsi_sender.jsonl"
        self.sender_stdout = (output / "apsi_sender_stdout.txt").open("wb")
        self.sender_stderr = (output / "apsi_sender_stderr.txt").open("wb")
        server_started = time.perf_counter_ns()
        self.sender = subprocess.Popen(
            [str(args.apsi_sender), "--db", str(args.apsi_db),
             "--metrics", str(self.sender_metrics), "--port", str(args.port)],
            stdout=self.sender_stdout, stderr=self.sender_stderr,
        )
        time.sleep(args.sender_ready_wait_ms / 1000)
        self.sender_startup_ms = (time.perf_counter_ns() - server_started) / 1e6
        receiver_started = time.perf_counter_ns()
        self.psi = RealLabeledAPSIClient(
            args.apsi_receiver, f"tcp://127.0.0.1:{args.port}",
            expected_sha256=args.apsi_receiver_sha256,
        )
        self.receiver_process_start_ms = (time.perf_counter_ns() - receiver_started) / 1e6
        pir_started = time.perf_counter_ns()
        self.pir = PersistentSimplePIRArtifactClient(
            args.simplepir, args.pir_database, SCALE_RECORDS + 1,
            output / "simplepir", expected_sha256=args.simplepir_sha256,
        )
        self.pir_process_start_to_ready_ms = (time.perf_counter_ns() - pir_started) / 1e6
        self.codec = ProvisionedAgentArtifactCodec(args.aead_key.read_bytes(), STORE_EPOCH)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="v15b-real")
        self.previous_agent: int | None = None
        self.previous_row = DUMMY_PIR_ROW

    def reset_pipeline(self) -> None:
        self.previous_agent = None
        self.previous_row = DUMMY_PIR_ROW

    def close(self) -> None:
        self.executor.shutdown(wait=True)
        self.pir.close(); self.psi.close(); self.sender.terminate()
        try: self.sender.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.sender.kill(); self.sender.wait(timeout=10)
        self.sender_stdout.close(); self.sender_stderr.close()

    def _psi(self, agent_id: int | None) -> tuple[Any, int, int]:
        started = time.perf_counter_ns(); result = self.psi.query(agent_id)
        return result, started, time.perf_counter_ns()

    def _pir(self, row: int) -> tuple[Any, int, int]:
        self.ordinal += 1
        operation = f"v15b-real-{self.ordinal:07d}"
        started = time.perf_counter_ns(); result = self.pir.query(operation, row)
        return result, started, time.perf_counter_ns()

    def slot(self, case: str, phase: str, repetition: int) -> dict[str, Any]:
        agent = case_agent(case)
        previous_agent, requested_row = self.previous_agent, self.previous_row
        cpu_before = {
            "sender": proc_cpu_ms(self.sender.pid), "receiver": proc_cpu_ms(self.psi.process.pid),
            "pir": proc_cpu_ms(self.pir.process.pid),
        }
        wall_started = time.perf_counter_ns()
        psi_future = self.executor.submit(self._psi, agent)
        pir_future = self.executor.submit(self._pir, requested_row)
        psi, psi_started, psi_ended = psi_future.result()
        pir, pir_started, pir_ended = pir_future.result()
        wall_ended = time.perf_counter_ns()
        label_started = time.perf_counter_ns()
        row = DUMMY_PIR_ROW
        if psi.row_handle is not None:
            handle = PIRRowHandle.decode(psi.row_handle.encode())
            if handle.store_epoch != STORE_EPOCH or handle.row_index == DUMMY_PIR_ROW:
                raise RuntimeError("invalid APSI row handle")
            row = handle.row_index
        label_decode_ns = time.perf_counter_ns() - label_started
        artifact_decode_ns = 0
        if previous_agent is not None and requested_row != DUMMY_PIR_ROW:
            decode_started = time.perf_counter_ns()
            artifact = self.codec.decode(pir.row, previous_agent)
            artifact_decode_ns = time.perf_counter_ns() - decode_started
            if artifact.canonical_agent_id != previous_agent:
                raise RuntimeError("pipeline artifact AgentID mismatch")
        if case != "DEPLOYED" and psi.row_handle is not None:
            raise RuntimeError("miss/idle unexpectedly matched APSI")
        if case == "DEPLOYED" and psi.row_handle is None:
            raise RuntimeError("deployed Agent missed APSI")
        self.previous_agent, self.previous_row = agent, row
        cpu_after = {
            "sender": proc_cpu_ms(self.sender.pid), "receiver": proc_cpu_ms(self.psi.process.pid),
            "pir": proc_cpu_ms(self.pir.process.pid),
        }
        return {
            "phase": phase, "private_mix": "", "private_case": case,
            "repetition": repetition, "global_ordinal": self.ordinal,
            "scheduled_time_ns": "", "actual_start_ns": wall_started,
            "psi_start_ns": psi_started, "psi_end_ns": psi_ended,
            "pir_start_ns": pir_started, "pir_end_ns": pir_ended,
            "actual_end_ns": wall_ended,
            "psi_stage_ms": (psi_ended - psi_started) / 1e6,
            "pir_stage_ms": (pir_ended - pir_started) / 1e6,
            "overlapped_slot_work_ms": (wall_ended - wall_started) / 1e6,
            "psi_completion_lateness_ms": "", "pir_completion_lateness_ms": "",
            "slot_completion_lateness_ms": "", "start_lateness_ms": "",
            "next_stage_ready": True, "public_queue_depth": 0, "slot_miss": False,
            "apsi_oprf_ms": psi.wire.oprf_ns / 1e6,
            "apsi_query_construction_ms": psi.wire.query_construction_ns / 1e6,
            "apsi_query_roundtrip_ms": psi.wire.query_roundtrip_ns / 1e6,
            "apsi_result_processing_ms": psi.wire.result_processing_ns / 1e6,
            "apsi_label_decode_ms": label_decode_ns / 1e6,
            "artifact_decode_ms": artifact_decode_ns / 1e6,
            "apsi_oprf_request_bytes": psi.wire.oprf_request_bytes,
            "apsi_oprf_response_bytes": psi.wire.oprf_response_bytes,
            "apsi_query_bytes": psi.wire.query_request_bytes,
            "apsi_result_bytes": psi.wire.query_response_bytes,
            "simplepir_query_bytes": pir.query_bytes, "simplepir_answer_bytes": pir.answer_bytes,
            "wire_bytes": psi.wire.oprf_request_bytes + psi.wire.oprf_response_bytes
            + psi.wire.query_request_bytes + psi.wire.query_response_bytes
            + pir.query_bytes + pir.answer_bytes,
            "pir_query_sha256": pir.query_sha256, "correct": pir.correct,
            "sender_cpu_ms": cpu_after["sender"] - cpu_before["sender"],
            "receiver_cpu_ms": cpu_after["receiver"] - cpu_before["receiver"],
            "pir_cpu_ms": cpu_after["pir"] - cpu_before["pir"],
            "sender_peak_rss_kib": proc_peak_rss_kib(self.sender.pid),
            "receiver_peak_rss_kib": proc_peak_rss_kib(self.psi.process.pid),
            "pir_peak_rss_kib": proc_peak_rss_kib(self.pir.process.pid),
        }


def sequences(count: int, seed: int) -> dict[str, list[str]]:
    rng = random.Random(seed)
    return {
        "ALL_IDLE": ["IDLE"] * count,
        "ALL_DEPLOYED": ["DEPLOYED"] * count,
        "ALL_UNPROVISIONED": ["UNPROVISIONED"] * count,
        "ALTERNATING": ["DEPLOYED" if i % 2 == 0 else "UNPROVISIONED" for i in range(count)],
        "RANDOMIZED": [rng.choice(CASES) for _ in range(count)],
    }


def run_pipeline(args: argparse.Namespace, output: Path) -> None:
    harness = RealPipelineHarness(args, output)
    rows: list[dict[str, Any]] = []
    try:
        # Cold slot is recorded separately and excluded from warm distributions.
        harness.reset_pipeline(); rows.append(harness.slot("IDLE", "COLD_SLOT", 1))
        for mix, values in sequences(args.pipeline_slots, 0x15B0).items():
            harness.reset_pipeline()
            for index, case in enumerate(values, 1):
                row = harness.slot(case, "WARM_PIPELINE", index)
                row["private_mix"] = mix; rows.append(row)
    finally:
        harness.close()
    if any(int(row["wire_bytes"]) != WIRE_BYTES for row in rows):
        raise RuntimeError("persistent transport changed the public wire size")
    if len({row["pir_query_sha256"] for row in rows}) != len(rows):
        raise RuntimeError("SimplePIR query transcript randomness was reused")
    csv_write(output / "V15B_PIPELINE_BENCHMARK.csv", rows)
    warm = [row for row in rows if row["phase"] == "WARM_PIPELINE"]
    summary = {
        "schema": "AgentTool.V15BPipelineBenchmarkSummary/1",
        "services": {
            "persistent": True, "per_slot_process_startup": False,
            "sender_start_to_measurement_ready_wait_ms": harness.sender_startup_ms,
            "receiver_process_start_ms": harness.receiver_process_start_ms,
            "simplepir_process_start_to_preprocessed_ready_ms": harness.pir_process_start_to_ready_ms,
        },
        "cold_slot_ms": rows[0]["overlapped_slot_work_ms"],
        "warm_slots": len(warm), "slots_per_mix": args.pipeline_slots,
        "fresh_simplepir_query_transcripts": len({row["pir_query_sha256"] for row in rows}),
        "psi_stage_ms": summarize([float(row["psi_stage_ms"]) for row in warm]),
        "pir_stage_ms": summarize([float(row["pir_stage_ms"]) for row in warm]),
        "overlapped_slot_work_ms": summarize([float(row["overlapped_slot_work_ms"]) for row in warm]),
        "wire_bytes_per_slot": WIRE_BYTES,
        "resource_peaks_kib": {
            "apsi_sender": max(int(row["sender_peak_rss_kib"]) for row in rows),
            "apsi_receiver": max(int(row["receiver_peak_rss_kib"]) for row in rows),
            "simplepir": max(int(row["pir_peak_rss_kib"]) for row in rows),
            "orchestrator": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
    }
    (output / "pipeline_summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def run_cadence(args: argparse.Namespace, output: Path) -> None:
    harness = RealPipelineHarness(args, output)
    rows: list[dict[str, Any]] = []
    try:
        # One unreported warmup establishes connections; it is not reused.
        harness.reset_pipeline(); harness.slot("IDLE", "CADENCE_WARMUP", 0)
        base_sequence = sequences(args.cadence_slots, 0x15B1)["RANDOMIZED"]
        for cadence in args.cadence_ms:
            harness.reset_pipeline()
            origin = time.monotonic_ns() + args.initial_lead_ms * 1_000_000
            for index, case in enumerate(base_sequence):
                scheduled = origin + index * cadence * 1_000_000
                now = time.monotonic_ns()
                if now < scheduled: time.sleep((scheduled - now) / 1e9)
                row = harness.slot(case, f"CADENCE_{cadence}MS", index + 1)
                deadline = scheduled + cadence * 1_000_000
                row["private_mix"] = "FROZEN_RANDOMIZED"
                row["scheduled_time_ns"] = scheduled
                row["start_lateness_ms"] = max(0, int(row["actual_start_ns"]) - scheduled) / 1e6
                row["psi_completion_lateness_ms"] = max(0, int(row["psi_end_ns"]) - deadline) / 1e6
                row["pir_completion_lateness_ms"] = max(0, int(row["pir_end_ns"]) - deadline) / 1e6
                row["slot_completion_lateness_ms"] = max(0, int(row["actual_end_ns"]) - deadline) / 1e6
                elapsed_slots = max(0, (int(row["actual_start_ns"]) - origin) // (cadence * 1_000_000))
                row["public_queue_depth"] = max(0, int(elapsed_slots) - index)
                row["slot_miss"] = int(row["actual_end_ns"]) > deadline
                row["cadence_ms"] = cadence
                rows.append(row)
    finally:
        harness.close()
    csv_write(output / "V15B_CADENCE_STRESS_RESULTS.csv", rows)
    summary: dict[str, Any] = {
        "schema": "AgentTool.V15BCadenceStressSummary/1",
        "slots_per_candidate": args.cadence_slots, "candidates_ms": args.cadence_ms,
        "identical_private_sequence_sha256": hashlib.sha256(
            json.dumps(base_sequence, separators=(",", ":")).encode()
        ).hexdigest(),
        "candidates": {},
    }
    for cadence in args.cadence_ms:
        selected = [row for row in rows if row["cadence_ms"] == cadence]
        summary["candidates"][str(cadence)] = {
            "slots": len(selected), "slot_misses": sum(bool(row["slot_miss"]) for row in selected),
            "max_start_lateness_ms": max(float(row["start_lateness_ms"]) for row in selected),
            "max_completion_lateness_ms": max(float(row["slot_completion_lateness_ms"]) for row in selected),
            "max_public_queue_depth": max(int(row["public_queue_depth"]) for row in selected),
            "final_start_lateness_ms": float(selected[-1]["start_lateness_ms"]),
            "slot_work_ms": summarize([float(row["overlapped_slot_work_ms"]) for row in selected]),
        }
    (output / "cadence_summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pipeline", "cadence"), required=True)
    parser.add_argument("--apsi-sender", type=Path, required=True)
    parser.add_argument("--apsi-receiver", type=Path, required=True)
    parser.add_argument("--apsi-db", type=Path, required=True)
    parser.add_argument("--simplepir", type=Path, required=True)
    parser.add_argument("--pir-database", type=Path, required=True)
    parser.add_argument("--aead-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=12265)
    parser.add_argument("--apsi-receiver-sha256")
    parser.add_argument("--simplepir-sha256")
    parser.add_argument("--sender-ready-wait-ms", type=int, default=1000)
    parser.add_argument("--pipeline-slots", type=int, default=500)
    parser.add_argument("--cadence-slots", type=int, default=1000)
    parser.add_argument("--cadence-ms", type=int, nargs="+", default=[150, 200, 250, 350])
    parser.add_argument("--initial-lead-ms", type=int, default=25)
    args = parser.parse_args()
    if args.pipeline_slots < 500 or args.cadence_slots < 1000:
        raise ValueError("V15B denominators are 500 pipeline slots/mix and 1000 slots/cadence")
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    if args.mode == "pipeline": run_pipeline(args, output)
    else: run_cadence(args, output)


if __name__ == "__main__":
    main()

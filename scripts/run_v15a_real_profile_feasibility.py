from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import resource
import subprocess
import time
from pathlib import Path
from typing import Any

from v14_provisioned_agents.artifact import ProvisionedAgentArtifactCodec
from v14_provisioned_agents.fixtures import DUMMY_PIR_ROW, SCALE_RECORDS, STORE_EPOCH
from v14_provisioned_agents.models import PIRRowHandle
from v14_provisioned_agents.psi import RealLabeledAPSIClient
from v14_provisioned_agents.simplepir import PersistentSimplePIRArtifactClient


CURRENT_SLOTS = 100
CURRENT_INTERVAL_MS = 60
CURRENT_EPOCH_MS = 6000
CURRENT_INITIAL_LEAD_MS = 25
CURRENT_MAX_REAL = 6
CASES = ("DEPLOYED", "UNPROVISIONED", "IDLE")


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


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


def proc_rss_kib(pid: int) -> int:
    values: dict[str, int] = {}
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith(("VmRSS:", "VmHWM:")):
            key, value, *_ = line.split()
            values[key.rstrip(":")] = int(value)
    return values.get("VmHWM", values.get("VmRSS", 0))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class Harness:
    def __init__(self, args: argparse.Namespace, output: Path):
        self.args = args
        self.output = output
        self.ordinal = 0
        self.rows: list[dict[str, Any]] = []
        self.sender_metrics = output / "V15A_RAW_APSI_SENDER.jsonl"
        self.sender_stdout = (output / "apsi_sender_stdout.txt").open("wb")
        self.sender_stderr = (output / "apsi_sender_stderr.txt").open("wb")
        self.sender = subprocess.Popen(
            [
                str(args.apsi_sender),
                "--db", str(args.apsi_db),
                "--metrics", str(self.sender_metrics),
                "--port", str(args.port),
            ],
            stdout=self.sender_stdout,
            stderr=self.sender_stderr,
        )
        time.sleep(1)
        self.psi = RealLabeledAPSIClient(
            args.apsi_receiver,
            f"tcp://127.0.0.1:{args.port}",
            expected_sha256=args.apsi_receiver_sha256,
        )
        self.pir = PersistentSimplePIRArtifactClient(
            args.simplepir,
            args.pir_database,
            SCALE_RECORDS + 1,
            output / "simplepir",
            expected_sha256=args.simplepir_sha256,
        )
        self.codec = ProvisionedAgentArtifactCodec(args.aead_key.read_bytes(), STORE_EPOCH)

    def close(self) -> None:
        self.pir.close()
        self.psi.close()
        self.sender.terminate()
        try:
            self.sender.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.sender.kill()
            self.sender.wait(timeout=10)
        self.sender_stdout.close()
        self.sender_stderr.close()

    def run_slot(self, case: str, phase: str, repetition: int) -> dict[str, Any]:
        if case == "DEPLOYED":
            agent_id = 101
        elif case == "UNPROVISIONED":
            agent_id = 1_000_101
        elif case == "IDLE":
            agent_id = None
        else:
            raise ValueError(case)
        self.ordinal += 1
        before = {
            "sender": proc_cpu_ms(self.sender.pid),
            "receiver": proc_cpu_ms(self.psi.process.pid),
            "pir": proc_cpu_ms(self.pir.process.pid),
        }
        total_started = time.perf_counter_ns()
        psi_started = time.perf_counter_ns()
        psi = self.psi.query(agent_id)
        psi_wall_ns = time.perf_counter_ns() - psi_started
        label_started = time.perf_counter_ns()
        if psi.row_handle is not None:
            decoded = PIRRowHandle.decode(psi.row_handle.encode())
            if decoded != psi.row_handle:
                raise RuntimeError("PSI label decode mismatch")
            row_index = decoded.row_index
        else:
            row_index = DUMMY_PIR_ROW
        label_decode_ns = time.perf_counter_ns() - label_started
        pir_started = time.perf_counter_ns()
        pir = self.pir.query(f"v15a-{self.ordinal:05d}", row_index)
        pir_wall_ns = time.perf_counter_ns() - pir_started
        artifact_decode_ns = 0
        if case == "DEPLOYED":
            if psi.row_handle is None or psi.row_handle.row_index == DUMMY_PIR_ROW:
                raise RuntimeError("deployed query did not return a real row")
            decode_started = time.perf_counter_ns()
            artifact = self.codec.decode(pir.row, agent_id)
            artifact_decode_ns = time.perf_counter_ns() - decode_started
            if artifact.canonical_agent_id != agent_id:
                raise RuntimeError("retrieved artifact AgentID mismatch")
        elif psi.row_handle is not None:
            raise RuntimeError("miss/idle query unexpectedly matched")
        total_ns = time.perf_counter_ns() - total_started
        after = {
            "sender": proc_cpu_ms(self.sender.pid),
            "receiver": proc_cpu_ms(self.psi.process.pid),
            "pir": proc_cpu_ms(self.pir.process.pid),
        }
        row = {
            "phase": phase,
            "case": case,
            "repetition": repetition,
            "global_ordinal": self.ordinal,
            "agent_id_private": "" if agent_id is None else agent_id,
            "pir_row_private": row_index,
            "apsi_oprf_ms": psi.wire.oprf_ns / 1e6,
            "apsi_query_construction_ms": psi.wire.query_construction_ns / 1e6,
            "apsi_query_roundtrip_ms": psi.wire.query_roundtrip_ns / 1e6,
            "apsi_result_processing_ms": psi.wire.result_processing_ns / 1e6,
            "apsi_label_decode_ms": label_decode_ns / 1e6,
            "apsi_total_wall_ms": psi_wall_ns / 1e6,
            "simplepir_total_wall_ms": pir_wall_ns / 1e6,
            "artifact_decode_ms": artifact_decode_ns / 1e6,
            "access_slot_total_ms": total_ns / 1e6,
            "apsi_oprf_request_bytes": psi.wire.oprf_request_bytes,
            "apsi_oprf_response_bytes": psi.wire.oprf_response_bytes,
            "apsi_query_bytes": psi.wire.query_request_bytes,
            "apsi_result_bytes": psi.wire.query_response_bytes,
            "simplepir_query_bytes": pir.query_bytes,
            "simplepir_answer_bytes": pir.answer_bytes,
            "message_count": 6,
            "protocol_round_count": 3,
            "query_sha256": pir.query_sha256,
            "correct": pir.correct,
            "sender_cpu_ms": after["sender"] - before["sender"],
            "receiver_cpu_ms": after["receiver"] - before["receiver"],
            "simplepir_cpu_ms": after["pir"] - before["pir"],
            "sender_peak_rss_kib": proc_rss_kib(self.sender.pid),
            "receiver_peak_rss_kib": proc_rss_kib(self.psi.process.pid),
            "simplepir_peak_rss_kib": proc_rss_kib(self.pir.process.pid),
        }
        self.rows.append(row)
        return row


def attach_server_components(output: Path, rows: list[dict[str, Any]]) -> None:
    sender = load_jsonl(output / "V15A_RAW_APSI_SENDER.jsonl")
    oprf = [x for x in sender if x.get("kind") == "OPRF"]
    query = [x for x in sender if x.get("kind") == "QUERY"]
    pir_client = load_jsonl(output / "simplepir" / "client_private_trace.jsonl")
    pir_server = load_jsonl(output / "simplepir" / "server_visible_trace.jsonl")
    if not (len(rows) == len(oprf) == len(query) == len(pir_client) == len(pir_server)):
        raise RuntimeError(
            f"trace cardinality mismatch rows={len(rows)} oprf={len(oprf)} query={len(query)} "
            f"pir_client={len(pir_client)} pir_server={len(pir_server)}"
        )
    for index, row in enumerate(rows):
        row["apsi_server_oprf_ms"] = int(oprf[index]["duration_ns"]) / 1e6
        row["apsi_server_evaluation_ms"] = int(query[index]["duration_ns"]) / 1e6
        row["simplepir_query_generation_ms"] = float(pir_client[index]["query_generation_ms"])
        row["simplepir_server_answer_ms"] = float(pir_server[index]["answer_ms"])
        row["simplepir_recovery_ms"] = float(pir_client[index]["recovery_ms"])
    # Preserve exact raw traces under V15A names.
    (output / "V15A_RAW_SIMPLEPIR_CLIENT.jsonl").write_text(
        (output / "simplepir" / "client_private_trace.jsonl").read_text(), encoding="utf-8"
    )
    (output / "V15A_RAW_SIMPLEPIR_SERVER.jsonl").write_text(
        (output / "simplepir" / "server_visible_trace.jsonl").read_text(), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apsi-sender", type=Path, required=True)
    parser.add_argument("--apsi-receiver", type=Path, required=True)
    parser.add_argument("--apsi-db", type=Path, required=True)
    parser.add_argument("--simplepir", type=Path, required=True)
    parser.add_argument("--pir-database", type=Path, required=True)
    parser.add_argument("--aead-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=12264)
    parser.add_argument("--apsi-receiver-sha256")
    parser.add_argument("--simplepir-sha256")
    parser.add_argument("--micro-repetitions", type=int, default=100)
    parser.add_argument("--schedule-repetitions", type=int, default=100)
    args = parser.parse_args()
    if args.micro_repetitions < 100 or args.schedule_repetitions < 100:
        raise ValueError("V15A requires at least 100 fresh slots per case and schedule mix")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    harness = Harness(args, output)
    scheduler_rows: list[dict[str, Any]] = []
    try:
        for case in CASES:
            for repetition in range(1, args.micro_repetitions + 1):
                harness.run_slot(case, "MICROBENCHMARK", repetition)

        rng = random.Random(0x153A)
        mixes = {
            "ALL_IDLE": ["IDLE"] * args.schedule_repetitions,
            "ALL_DEPLOYED": ["DEPLOYED"] * args.schedule_repetitions,
            "ALL_UNPROVISIONED": ["UNPROVISIONED"] * args.schedule_repetitions,
            "ALTERNATING": [CASES[i % len(CASES)] for i in range(args.schedule_repetitions)],
            "RANDOMIZED": [rng.choice(CASES) for _ in range(args.schedule_repetitions)],
        }
        reference_schedule = None
        for mix_name, sequence in mixes.items():
            origin_ns = time.monotonic_ns() + CURRENT_INITIAL_LEAD_MS * 1_000_000
            scheduled = [origin_ns + i * CURRENT_INTERVAL_MS * 1_000_000 for i in range(len(sequence))]
            relative = [(value - origin_ns) / 1e6 for value in scheduled]
            if reference_schedule is None:
                reference_schedule = relative
            elif relative != reference_schedule:
                raise RuntimeError("public scheduled timestamps changed across private mixes")
            for index, case in enumerate(sequence):
                now = time.monotonic_ns()
                if now < scheduled[index]:
                    time.sleep((scheduled[index] - now) / 1e9)
                actual_start = time.monotonic_ns()
                result = harness.run_slot(case, f"SCHEDULER_{mix_name}", index + 1)
                completed = time.monotonic_ns()
                lateness_ns = max(0, actual_start - scheduled[index])
                scheduled_so_far = min(
                    len(sequence), max(0, (actual_start - origin_ns) // (CURRENT_INTERVAL_MS * 1_000_000) + 1)
                )
                pending_including_current = max(1, int(scheduled_so_far) - index)
                scheduler_rows.append({
                    "mix": mix_name,
                    "slot": index,
                    "private_case": case,
                    "scheduled_offset_ms": relative[index],
                    "start_lateness_ms": lateness_ns / 1e6,
                    "completion_lateness_ms": max(0, completed - scheduled[index]) / 1e6,
                    "pending_queue_depth_including_current": pending_including_current,
                    "missed_nominal_interval": lateness_ns > CURRENT_INTERVAL_MS * 1_000_000,
                    "access_slot_total_ms": result["access_slot_total_ms"],
                })
    finally:
        harness.close()

    attach_server_components(output, harness.rows)
    write_csv(output / "V15A_REAL_ACCESS_SLOT_BENCHMARK.csv", harness.rows)
    write_csv(output / "V15A_SCHEDULER_CAPACITY.csv", scheduler_rows)
    (output / "V15A_RAW_ACCESS_SLOT_TRACE.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in harness.rows),
        encoding="utf-8",
    )

    micro = [row for row in harness.rows if row["phase"] == "MICROBENCHMARK"]
    summary: dict[str, Any] = {
        "schema": "AgentTool.V15ARealAccessSlotSummary/1",
        "profile_under_test": {
            "source": "V4R8 historical Registry profile applied as current Agent-access candidate",
            "slots": CURRENT_SLOTS,
            "interval_ms": CURRENT_INTERVAL_MS,
            "epoch_ms": CURRENT_EPOCH_MS,
            "initial_lead_ms": CURRENT_INITIAL_LEAD_MS,
            "maximum_real_agent_resolutions": CURRENT_MAX_REAL,
        },
        "microbenchmark_repetitions_per_case": args.micro_repetitions,
        "cases": {},
        "resource_peaks": {
            "sender_peak_rss_kib": max(row["sender_peak_rss_kib"] for row in harness.rows),
            "receiver_peak_rss_kib": max(row["receiver_peak_rss_kib"] for row in harness.rows),
            "simplepir_peak_rss_kib": max(row["simplepir_peak_rss_kib"] for row in harness.rows),
            "orchestrator_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
    }
    timing_fields = (
        "apsi_oprf_ms", "apsi_query_construction_ms", "apsi_server_evaluation_ms",
        "apsi_result_processing_ms", "apsi_label_decode_ms",
        "simplepir_query_generation_ms", "simplepir_server_answer_ms",
        "simplepir_recovery_ms", "access_slot_total_ms",
        "sender_cpu_ms", "receiver_cpu_ms", "simplepir_cpu_ms",
    )
    for case in CASES:
        selected = [row for row in micro if row["case"] == case]
        summary["cases"][case] = {
            "count": len(selected),
            **{field: summarize([float(row[field]) for row in selected]) for field in timing_fields},
        }
    all_total = [float(row["access_slot_total_ms"]) for row in micro]
    summary["all_cases_access_slot_total_ms"] = summarize(all_total)
    summary["unique_pir_query_transcripts"] = len({row["query_sha256"] for row in harness.rows})
    summary["total_slots_executed"] = len(harness.rows)
    (output / "V15A_REAL_ACCESS_SLOT_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    wire_rows = []
    for case in CASES:
        selected = [row for row in micro if row["case"] == case]
        fields = (
            "apsi_oprf_request_bytes", "apsi_oprf_response_bytes", "apsi_query_bytes",
            "apsi_result_bytes", "simplepir_query_bytes", "simplepir_answer_bytes",
            "message_count", "protocol_round_count",
        )
        values = {field: sorted({int(row[field]) for row in selected}) for field in fields}
        if any(len(value) != 1 for value in values.values()):
            raise RuntimeError(f"wire shape changed within {case}: {values}")
        scalar = {field: value[0] for field, value in values.items()}
        wire_rows.append({
            "case": case,
            **scalar,
            "psi_bytes": scalar["apsi_oprf_request_bytes"] + scalar["apsi_oprf_response_bytes"]
            + scalar["apsi_query_bytes"] + scalar["apsi_result_bytes"],
            "pir_bytes": scalar["simplepir_query_bytes"] + scalar["simplepir_answer_bytes"],
            "bytes_per_public_agent_access_slot": scalar["apsi_oprf_request_bytes"]
            + scalar["apsi_oprf_response_bytes"] + scalar["apsi_query_bytes"]
            + scalar["apsi_result_bytes"] + scalar["simplepir_query_bytes"]
            + scalar["simplepir_answer_bytes"],
        })
    write_csv(output / "V15A_WIRE_ACCOUNTING.csv", wire_rows)
    if len({tuple(row.items())[1:] for row in wire_rows}) != 1:
        # The case label is deliberately excluded from the comparison.
        comparable = [{k: v for k, v in row.items() if k != "case"} for row in wire_rows]
        if not (comparable[0] == comparable[1] == comparable[2]):
            raise RuntimeError("deployed/unprovisioned/idle wire structure differs")

    schedule_summary = {}
    for mix in sorted({row["mix"] for row in scheduler_rows}):
        selected = [row for row in scheduler_rows if row["mix"] == mix]
        schedule_summary[mix] = {
            "slots": len(selected),
            "missed_slots": sum(bool(row["missed_nominal_interval"]) for row in selected),
            "max_start_lateness_ms": max(float(row["start_lateness_ms"]) for row in selected),
            "max_queue_depth": max(int(row["pending_queue_depth_including_current"]) for row in selected),
            "final_completion_lateness_ms": float(selected[-1]["completion_lateness_ms"]),
            "scheduled_offsets_identical": [row["scheduled_offset_ms"] for row in selected]
            == [i * CURRENT_INTERVAL_MS for i in range(len(selected))],
        }
    (output / "V15A_SCHEDULER_SUMMARY.json").write_text(
        json.dumps(schedule_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

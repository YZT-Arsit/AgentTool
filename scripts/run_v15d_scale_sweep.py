from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v14_provisioned_agents.artifact import PIR_RECORD_BYTES, ProvisionedAgentArtifactCodec
from v14_provisioned_agents.fixtures import STORE_EPOCH, make_artifact, scale_row_for_agent
from v14_provisioned_agents.models import AgentFramework, PIRRowHandle
from v14_provisioned_agents.psi import RealLabeledAPSIClient, write_sender_input
from v14_provisioned_agents.simplepir import PersistentSimplePIRArtifactClient


SIZES = (1_000, 10_000, 50_000, 100_000)
REPETITIONS = 30
APSI_SHA = "fd088edc9a12760b8ba0a7fe86fe31db91f5714c3da8a0bbe74096e6767481e0"
PIR_SHA = "2ceacc5f772c908dfdd696cfdaf35e60ed6477f70d8a4367868ba0f0cfa0305b"


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values); position = (len(ordered) - 1) * q
    lo = int(position); hi = min(lo + 1, len(ordered) - 1); weight = position - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def timed_call(callable_: Any, *args: Any) -> tuple[Any, int, int]:
    started = time.monotonic_ns()
    result = callable_(*args)
    return result, started, time.monotonic_ns()


def rss_bytes(pid: int) -> int | None:
    status = Path(f"/proc/{pid}/status")
    if not status.exists():
        return None
    for line in status.read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return None


def build_store(root: Path, n: int, codec: ProvisionedAgentArtifactCodec) -> tuple[Path, Path, float]:
    pir = root / f"artifact_store_{n}_plus_dummy.bin"
    sender_input = root / f"apsi_sender_input_{n}.bin"
    started = time.monotonic()
    with pir.open("xb") as stream:
        stream.truncate((n + 1) * PIR_RECORD_BYTES)
        for agent_id in range(1, n + 1):
            framework = AgentFramework.OPENAI_AGENTS_SDK if agent_id % 2 else AgentFramework.MICROSOFT_AGENT_FRAMEWORK
            artifact = make_artifact(agent_id, framework, role=f"scale-template-{agent_id % 16:02d}", synthetic_scale=True)
            stream.seek(scale_row_for_agent(agent_id, n) * PIR_RECORD_BYTES); stream.write(codec.encode(artifact))
        stream.seek(n * PIR_RECORD_BYTES); stream.write(os.urandom(PIR_RECORD_BYTES))
    write_sender_input(((agent_id, PIRRowHandle(scale_row_for_agent(agent_id, n), STORE_EPOCH))
                        for agent_id in range(1, n + 1)), sender_input)
    return pir, sender_input, (time.monotonic() - started) * 1000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apsi-builder", type=Path, required=True)
    parser.add_argument("--apsi-params", type=Path, required=True)
    parser.add_argument("--apsi-sender", type=Path, required=True)
    parser.add_argument("--apsi-receiver", type=Path, required=True)
    parser.add_argument("--simplepir", type=Path, required=True)
    parser.add_argument("--aead-key", type=Path, required=True)
    parser.add_argument("--reuse-100k-apsi-db", type=Path, required=True)
    parser.add_argument("--reuse-100k-pir-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-port", type=int, default=12860)
    args = parser.parse_args(); output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    codec = ProvisionedAgentArtifactCodec(args.aead_key.read_bytes(), STORE_EPOCH)
    rows: list[dict[str, Any]] = []
    for size_index, n in enumerate(SIZES):
        case = output / f"N{n}"; case.mkdir()
        if n == 100_000:
            pir_db, apsi_db, construction_ms = args.reuse_100k_pir_db, args.reuse_100k_apsi_db, None
            apsi_build = json.loads((args.reuse_100k_apsi_db.parent / "apsi_sender_build_stats.json").read_text())
        else:
            pir_db, sender_input, construction_ms = build_store(case, n, codec)
            apsi_db = case / "apsi_sender_db.bin"; stats = case / "apsi_sender_build_stats.json"
            subprocess.run([str(args.apsi_builder), str(args.apsi_params), str(sender_input), str(apsi_db), str(stats)], check=True)
            apsi_build = json.loads(stats.read_text())
        port = args.base_port + size_index
        sender_metrics = case / "apsi_sender.jsonl"
        sender_started = time.monotonic_ns()
        sender = subprocess.Popen(
            [str(args.apsi_sender), "--db", str(apsi_db), "--metrics", str(sender_metrics), "--port", str(port)],
            stdout=(case / "apsi_sender_stdout.txt").open("wb"), stderr=(case / "apsi_sender_stderr.txt").open("wb"),
        ); time.sleep(1)
        sender_startup_ms = (time.monotonic_ns() - sender_started) / 1e6
        psi_ms: list[float] = []; pir_ms: list[float] = []; combined_ms: list[float] = []
        wire_values = set()
        try:
            services_started = time.monotonic_ns()
            with RealLabeledAPSIClient(args.apsi_receiver, f"tcp://127.0.0.1:{port}", expected_sha256=APSI_SHA) as psi, \
                 PersistentSimplePIRArtifactClient(args.simplepir, pir_db, n + 1, case / "simplepir", expected_sha256=PIR_SHA) as pir, \
                 ThreadPoolExecutor(max_workers=2) as pool:
                persistent_services_startup_ms = (time.monotonic_ns() - services_started) / 1e6
                apsi_sender_rss_bytes = rss_bytes(sender.pid)
                simplepir_server_rss_bytes = rss_bytes(pir.process.pid)
                for repetition in range(REPETITIONS + 2):
                    agent_id = 1 + ((repetition * 7919 + 17) % n); row = scale_row_for_agent(agent_id, n)
                    slot_started = time.monotonic_ns()
                    psi_future = pool.submit(timed_call, psi.query, agent_id)
                    pir_future = pool.submit(timed_call, pir.query, f"V15D-SCALE-{n}-{repetition}", row)
                    psi_result, psi_started, psi_done = psi_future.result()
                    pir_result, pir_started, pir_done = pir_future.result()
                    done = max(psi_done, pir_done)
                    if not pir_result.correct or psi_result.row_handle is None: raise RuntimeError("real scale query failed")
                    wire_values.add((psi_result.wire.oprf_request_bytes, psi_result.wire.oprf_response_bytes,
                                     psi_result.wire.query_request_bytes, psi_result.wire.query_response_bytes,
                                     pir_result.query_bytes, pir_result.answer_bytes))
                    if repetition >= 2:
                        psi_ms.append((psi_done - psi_started) / 1e6)
                        pir_ms.append((pir_done - pir_started) / 1e6)
                        combined_ms.append((done - slot_started) / 1e6)
        finally:
            sender.terminate()
            try: sender.wait(timeout=30)
            except subprocess.TimeoutExpired: sender.kill(); sender.wait(timeout=10)
        pir_ready = json.loads((case / "simplepir/preprocessing_ready.json").read_text())
        wire = next(iter(wire_values)) if len(wire_values) == 1 else None
        if wire is None: raise RuntimeError("wire shape changed within scale coordinate")
        rows.append({
            "N": n, "schema_valid_artifacts": n, "real_world_unique_agents": False,
            "queries": REPETITIONS, "dataset_construction_ms": construction_ms,
            "apsi_preprocessing_ms": (
                float(apsi_build["preprocessing_ns"]) / 1e6
                if "preprocessing_ns" in apsi_build
                else apsi_build.get("build_ms") or apsi_build.get("total_ms")
            ),
            "apsi_sender_db_bytes": apsi_db.stat().st_size,
            "apsi_sender_startup_ms": sender_startup_ms,
            "persistent_services_startup_ms": persistent_services_startup_ms,
            "apsi_sender_rss_bytes": apsi_sender_rss_bytes,
            "simplepir_server_rss_bytes": simplepir_server_rss_bytes,
            "pir_database_bytes": pir_db.stat().st_size,
            "pir_database_construction_ms": pir_ready.get("database_construction_ms"),
            "pir_full_preprocessing_setup_ms": pir_ready.get("full_preprocessing_setup_ms"),
            "psi_online_p50_ms": percentile(psi_ms, .5), "psi_online_p95_ms": percentile(psi_ms, .95),
            "pir_online_p50_ms": percentile(pir_ms, .5), "pir_online_p95_ms": percentile(pir_ms, .95),
            "combined_pipelined_p50_ms": percentile(combined_ms, .5),
            "combined_pipelined_p95_ms": percentile(combined_ms, .95),
            "apsi_oprf_request_bytes": wire[0], "apsi_oprf_response_bytes": wire[1],
            "apsi_query_bytes": wire[2], "apsi_result_bytes": wire[3],
            "simplepir_query_bytes": wire[4], "simplepir_answer_bytes": wire[5],
            "wire_bytes_per_access": sum(wire),
        })
        print(json.dumps({"N": n, "complete": True, "p50_ms": rows[-1]["combined_pipelined_p50_ms"]}), flush=True)
    keys = list(rows[0])
    with (output / "FINAL_SCALE_RESULTS.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys); writer.writeheader(); writer.writerows(rows)
    (output / "SCALE_SUMMARY.json").write_text(json.dumps({"schema": "AgentTool.V15DScaleSweep/1", "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()

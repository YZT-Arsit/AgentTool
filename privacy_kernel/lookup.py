from __future__ import annotations

import hashlib
import json
import secrets
import struct
from dataclasses import dataclass
from pathlib import Path

from agent_control_virtualization.ir import AgentCapsule, CAPSULE_BYTES
from cryptographic_closure.pir_backend import (PIRRequest, SIMPLEPIR_COMMIT,
                                               read_raw_queries,
                                               recovered_capsules,
                                               run_simplepir)


@dataclass(frozen=True)
class PIRSlotResult:
    slot: int
    needed_index: int | None
    queried_dummy: bool
    capsule: AgentCapsule


@dataclass(frozen=True)
class CanonicalPIRAudit:
    backend: str
    commit: str
    slots: int
    real_queries: int
    dummy_queries: int
    correct_queries: int
    fresh_queries: bool
    server_trace_has_private_index: bool


def write_capsule_registry(path: Path, record_count: int,
                           capsules: dict[int, AgentCapsule]) -> str:
    """Physically instantiate fixed rows; generated rows are scale padding."""
    if record_count < 2 or any(not 0 <= index < record_count for index in capsules):
        raise ValueError("invalid registry dimensions")
    if not capsules:
        raise ValueError("at least one real capsule is required")
    prototype = next(iter(capsules.values())).serialize()
    digest = hashlib.sha256()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for index in range(record_count):
            row = bytearray(capsules[index].serialize() if index in capsules else prototype)
            # Fixed capsule ABI logical_agent_id is offset 8, network order.
            struct.pack_into("!I", row, 8, index)
            handle.write(row)
            digest.update(row)
    if path.stat().st_size != record_count * CAPSULE_BYTES:
        raise AssertionError("registry was not physically instantiated")
    return digest.hexdigest()


class SimplePIRLookupSchedule:
    """Trusted client scheduler using the pinned official SimplePIR bridge."""

    def __init__(self, root: Path, registry: Path, record_count: int,
                 output_dir: Path, reserved_dummy_rows: tuple[int, ...]):
        if not reserved_dummy_rows or any(not 0 <= row < record_count for row in reserved_dummy_rows):
            raise ValueError("invalid reserved dummy rows")
        self.root = root
        self.registry = registry
        self.record_count = record_count
        self.output_dir = output_dir
        self.reserved_dummy_rows = reserved_dummy_rows

    def execute(self, pending_indices: list[int | None]) -> tuple[list[PIRSlotResult], CanonicalPIRAudit]:
        requests: list[PIRRequest] = []
        chosen: list[tuple[int | None, int]] = []
        for slot, needed in enumerate(pending_indices):
            if needed is None:
                query_index = secrets.choice(self.reserved_dummy_rows)
                private_class = "DUMMY"
            else:
                if needed in self.reserved_dummy_rows or not 0 <= needed < self.record_count:
                    raise ValueError("real lookup index is invalid or reserved")
                query_index = needed
                private_class = "REAL"
            chosen.append((needed, query_index))
            requests.append(PIRRequest("canonical-pir", slot, query_index, private_class))
        artifacts = run_simplepir(self.root, self.registry, self.record_count,
                                  requests, self.output_dir)
        capsules = recovered_capsules(artifacts)
        raw_queries = read_raw_queries(artifacts.raw_query_path)
        if len(raw_queries) != len(requests) or len({hashlib.sha256(value).digest() for value in raw_queries}) != len(raw_queries):
            raise AssertionError("PIR slots did not use fresh query randomness")
        server_raw = (self.output_dir / "server_visible_trace.jsonl").read_text(encoding="utf-8").lower()
        forbidden = any(term in server_raw for term in
                        ("private_index", "agent_name", "logical_agent", "private_class"))
        if forbidden:
            raise AssertionError("private target entered the PIR server trace")
        results = [PIRSlotResult(slot, needed, needed is None, capsule)
                   for slot, ((needed, _), capsule) in enumerate(zip(chosen, capsules, strict=True))]
        metrics = artifacts.metrics
        audit = CanonicalPIRAudit(
            backend=str(metrics["backend"]), commit=str(metrics["commit"]), slots=len(results),
            real_queries=sum(item.needed_index is not None for item in results),
            dummy_queries=sum(item.queried_dummy for item in results),
            correct_queries=int(metrics["correct_queries"]),
            fresh_queries=bool(metrics["fresh_repeated_queries"]),
            server_trace_has_private_index=forbidden,
        )
        public_summary = {
            "backend": audit.backend, "commit": audit.commit, "slots": audit.slots,
            "query_bytes": metrics["online_upload_bytes"],
            "answer_bytes": metrics["online_download_bytes"],
            "logical_records": metrics["logical_records"],
        }
        (self.output_dir / "canonical_public_pir_summary.json").write_text(
            json.dumps(public_summary, indent=2), encoding="utf-8")
        return results, audit


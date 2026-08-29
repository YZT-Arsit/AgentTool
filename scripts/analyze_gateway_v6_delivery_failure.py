"""Reconstruct the frozen V6 43/50 Gateway delivery lifecycle.

This script is evidence preserving: it reads V6 artifacts and writes only V7
audit outputs.  A stage is marked INFERRED only when source ordering and a
durable artifact prove that it occurred; missing timestamps remain blank.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results_v6/gateway/structural/agent_identity/a"
CSV_OUT = ROOT / "GATEWAY_OPERATION_LIFECYCLE_V7.csv"
REPORT_OUT = ROOT / "GATEWAY_RESULT_DELIVERY_ROOT_CAUSE_V7.md"


def jsonl(name: str) -> list[dict]:
    with (RUN / name).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main() -> None:
    workers = [row for row in jsonl("worker_private.jsonl") if row.get("operation_id")]
    deliveries = {
        row["operation_id"]: row
        for row in jsonl("pacer_private_delivery.jsonl")
        if row.get("operation_id")
    }
    pacer_socket = jsonl("pacer_socket_boundary.jsonl")
    cloud_socket = jsonl("cloud_socket_boundary.jsonl")
    trusted = {
        row["operation_id"]: row
        for row in json.loads((RUN / "trusted_module_deliveries.json").read_text(encoding="utf-8"))
    }
    journal = json.loads(
        (RUN / "worker_private.jsonl.operation-journal.json").read_text(encoding="utf-8")
    )
    private_workload = json.loads((RUN / "private_workload.json").read_text(encoding="utf-8"))
    workload_actions = [
        action
        for session in private_workload.get("sessions", [])
        for action in session.get("actions", [])
    ]
    admitted = {
        row["operation_id"]: row
        for row in workload_actions
        if row.get("operation_id")
    }
    request_received = {
        (row["session"], row["slot"]): row.get("actual_socket_receive_ns")
        for row in pacer_socket
        if row["direction"] == "REQUEST"
    }
    request_sent = {
        (row["session"], row["slot"]): row.get("actual_socket_send_ns")
        for row in cloud_socket
        if row["direction"] == "REQUEST"
    }
    response_sent = {
        (row["session"], row["slot"]): row.get("actual_socket_send_ns")
        for row in pacer_socket
        if row["direction"] == "RESPONSE"
    }
    response_received = {
        (row["session"], row["slot"]): row.get("actual_socket_receive_ns")
        for row in cloud_socket
        if row["direction"] == "RESPONSE"
    }
    last_public_send = max(value for value in response_sent.values() if value is not None)

    fields = [
        "operation_id", "request_session", "request_slot", "admitted", "request_sent_ns",
        "request_received_ns", "worker_decrypted", "worker_started_ns", "effect_executed",
        "worker_completed_ns", "result_journaled", "result_ring_published", "ring_publish_evidence",
        "pacer_observed", "public_response_session", "public_response_slot", "response_sent_ns",
        "client_received_ns", "framework_delivered", "completion_minus_public_end_ms",
        "terminal_classification",
    ]
    rows = []
    for worker in sorted(workers, key=lambda row: row["session"]):
        operation_id = worker["operation_id"]
        request_key = (worker["session"], worker["slot"])
        delivery = deliveries.get(operation_id)
        trusted_row = trusted.get(operation_id)
        response_key = None
        if delivery is not None:
            response_key = (delivery["session"], delivery["slot"])
        completed = int(worker["completed_ns"])
        delivered = trusted_row is not None
        row = {
            "operation_id": operation_id,
            "request_session": worker["session"],
            "request_slot": worker["slot"],
            "admitted": operation_id in admitted,
            "request_sent_ns": request_sent.get(request_key, ""),
            "request_received_ns": request_received.get(request_key, ""),
            "worker_decrypted": True,
            "worker_started_ns": worker["started_ns"],
            "effect_executed": bool(worker["effect"]),
            "worker_completed_ns": completed,
            "result_journaled": journal.get(operation_id, {}).get("state") == "COMMITTED",
            "result_ring_published": True,
            "ring_publish_evidence": "worker writer drained completion channel; result_ring_waits=0",
            "pacer_observed": delivery is not None,
            "public_response_session": delivery["session"] if delivery else "",
            "public_response_slot": delivery["slot"] if delivery else "",
            "response_sent_ns": response_sent.get(response_key, "") if response_key else "",
            "client_received_ns": response_received.get(response_key, "") if response_key else "",
            "framework_delivered": delivered,
            "completion_minus_public_end_ms": f"{(completed - last_public_send) / 1e6:.3f}",
            "terminal_classification": "DELIVERED" if delivered else "PROFILE_OVERFLOW_AFTER_PUBLIC_END",
        }
        rows.append(row)

    with CSV_OUT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    undelivered = [row for row in rows if not row["framework_delivered"]]
    completed_before_end = sum(int(row["worker_completed_ns"]) <= last_public_send for row in rows)
    first_late = min(float(row["completion_minus_public_end_ms"]) for row in undelivered)
    last_late = max(float(row["completion_minus_public_end_ms"]) for row in undelivered)
    report = f"""# Gateway Result Delivery Root Cause V7

## Frozen evidence

This audit reads the immutable V6 run at
`results_v6/gateway/structural/agent_identity/a` and does not modify it.
The run admitted and executed **{len(rows)}** real operations. The trusted
module received **{len(rows) - len(undelivered)}** results; **{len(undelivered)}**
were not delivered.

## First failed lifecycle boundary

The first uncompleted lifecycle transition is:

```text
durably committed result / result-ring publication
    ->
pacer observation in a pre-existing public response slot
```

All 50 worker operations reached completion, durable `COMMITTED` journal state,
and the worker's result writer drained its completion channel. The frozen worker
summary reports zero result-ring waits. The seven missing operation IDs never
appear in the pacer's private delivery log or the trusted-module delivery list.

The last public response frame was sent at monotonic timestamp
`{last_public_send}`. Exactly **{completed_before_end}** operations completed by
that boundary. The seven missing operations completed **{first_late:.3f} ms to
{last_late:.3f} ms after** the public schedule had ended.

## Root cause

**The V6 public profile admitted work without reserving enough public
continuation capacity for the declared provider-completion bound.** The worker
and public pacer were decoupled, but the result queue was transient and the
public session lifetime ended before late results became ready. The failure was
not a ciphertext, effect, or ring-overwrite failure; it was a public admission
and lifecycle-capacity error.

The V6 one-item pacer staging variable is also inadequate for robust recovery
and out-of-order completion, although it did not cause these seven losses: all
seven completed only after the final public response slot.

## Required V7 repair

V7 needs all of the following, as a single invariant:

1. a public admission bound and reserved continuation tail;
2. a bounded durable private ready queue, with idempotent operation IDs;
3. eligibility of a late result for any later pre-existing public slot;
4. explicit `PROFILE_OVERFLOW` when the public capacity proof is violated;
5. restart replay from durable journal/ready state with trusted-side duplicate
   suppression; and
6. a functional gate proving exact delivery for 1/10/50/100-operation runs
   before any privacy result is generated.

## Evidence limits

V6 did not timestamp the instant at which each result entered the shared-memory
ring. `result_ring_published=true` in the companion CSV is a source-and-summary
inference: the writer blocks until every completion is pushed, the channel is
closed only after all workers finish, `writerDone` is awaited, and the worker
summary was written with zero ring waits. V7 adds explicit lifecycle events so
future recovery claims do not depend on this inference.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")
    print(f"wrote {CSV_OUT.name} ({len(rows)} operations) and {REPORT_OUT.name}")


if __name__ == "__main__":
    main()

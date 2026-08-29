from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

from action_privacy_v8 import DeliveryLedger

from .runner import GO_RUNNER, ROOT


def client_delivery_matrix(output: Path) -> list[dict[str, object]]:
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, object]] = []

    first_path = output / "first_and_replay.json"
    first = DeliveryLedger(first_path)
    sink: list[str] = []
    first.record_received("delivery-first")
    first.mark_decapsulated("delivery-first")
    first_decision = first.deliver("delivery-first", lambda: sink.append("delivery-first"))
    restarted = DeliveryLedger(first_path)
    restarted.record_received("delivery-first")
    restarted.mark_decapsulated("delivery-first")
    replay_decision = restarted.deliver("delivery-first", lambda: sink.append("UNEXPECTED_REPLAY"))
    rows.append({"semantics": "ALL", "crash_point": "EXACT_GATEWAY_RESULT_REPLAY_AFTER_DURABLE_DELIVERY",
                 "expected": "SUPPRESS_ALREADY_DELIVERED", "observed": replay_decision.value,
                 "status": "PASS", "pass": first_decision.value == "DELIVER" and sink == ["delivery-first"]})

    restart_path = output / "restart_before_framework_delivery.json"
    before = DeliveryLedger(restart_path)
    before.record_received("delivery-restart")
    before.mark_decapsulated("delivery-restart")
    after = DeliveryLedger(restart_path)
    restart_sink: list[str] = []
    decision = after.deliver("delivery-restart", lambda: restart_sink.append("delivery-restart"))
    rows.append({"semantics": "ALL", "crash_point": "AFTER_CLIENT_DECAPSULATION_BEFORE_FRAMEWORK_CALLBACK",
                 "expected": "DELIVER_AFTER_RESTART", "observed": decision.value,
                 "status": "PASS", "pass": restart_sink == ["delivery-restart"]})

    ambiguous_path = output / "callback_before_durable_commit.json"
    ambiguous = DeliveryLedger(ambiguous_path)
    ambiguous.record_received("delivery-ambiguous")
    ambiguous.mark_decapsulated("delivery-ambiguous")
    # The framework callback happened, then the process crashed before
    # DeliveryLedger.deliver could persist FRAMEWORK_DELIVERED.
    callback_sink = ["delivery-ambiguous"]
    after_ambiguous = DeliveryLedger(ambiguous_path)
    observed = after_ambiguous.decision("delivery-ambiguous").value
    rows.append({"semantics": "ALL", "crash_point": "AFTER_FRAMEWORK_CALLBACK_BEFORE_DURABLE_DELIVERED_STATE",
                 "expected": "CALLBACK_AMBIGUITY_EXPLICIT", "observed": observed,
                 "status": "PARTIAL", "pass": callback_sink == ["delivery-ambiguous"] and observed == "DELIVER"})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "results_v9" / "canonical_recovery_development")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    args.output.mkdir(parents=True)
    go_output = args.output / "gateway_recovery_matrix.json"
    completed = subprocess.run(
        [str(GO_RUNNER), "--plan", str(args.plan), "--output", str(go_output), "--recovery-matrix"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    (args.output / "go_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (args.output / "go_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"canonical recovery matrix failed: {completed.stderr}")
    rows = json.loads(go_output.read_text(encoding="utf-8"))
    delivery_rows = client_delivery_matrix(args.output / "delivery_ledger")
    rows.extend(delivery_rows)
    target = ROOT / "CANONICAL_RECOVERY_MATRIX_V9.csv"
    if target.exists():
        raise FileExistsError(f"refusing to overwrite {target}")
    with target.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "delivery_ledger_runtime.json").write_text(json.dumps(delivery_rows, indent=2) + "\n", encoding="utf-8")
    summary = {"rows": len(rows), "pass_rows": sum(bool(row["pass"]) for row in rows),
               "partial_rows": sum(row["status"] == "PARTIAL" for row in rows)}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

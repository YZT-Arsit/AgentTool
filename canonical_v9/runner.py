from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from action_privacy_v8 import (
    ActionKind,
    ActionRouteDescriptor,
    AgentDescriptorV7,
    AgentDescriptorV7Codec,
    AgentServiceRouteDescriptor,
    DeliveryLedger,
    EffectSemantics,
    PlacementClass,
    PrivacyProfile,
    ProtectedActionIntent,
    TrustedActionRouter,
)
from action_privacy_v8.descriptor import AGENT_DESCRIPTOR_V7_BYTES
from cryptographic_closure.pir_backend import PIRRequest, run_simplepir


EPOCH = 20260829
GO_RUNNER = ROOT / "common_action_gateway_v2" / "bin" / "canonical-v9-runner"
if os.name == "nt":
    GO_RUNNER = GO_RUNNER.with_suffix(".exe")


@dataclass(frozen=True)
class CanonicalSessionSpec:
    case_id: str
    agent_capability: str
    agent_id: int
    action_intents: tuple[ProtectedActionIntent, ...]


ROUTES = {
    "tool.a": ActionRouteDescriptor("tool.a", "route-tool-a", ActionKind.TOOL, PlacementClass.EXTERNAL, EffectSemantics.READ_ONLY, "policy-tool-a"),
    "tool.b": ActionRouteDescriptor("tool.b", "route-tool-b", ActionKind.TOOL, PlacementClass.EXTERNAL, EffectSemantics.IDEMPOTENT_EFFECT, "policy-tool-b"),
    "tool.read": ActionRouteDescriptor("tool.read", "route-tool-read", ActionKind.TOOL, PlacementClass.EXTERNAL, EffectSemantics.READ_ONLY, "policy-tool-read"),
    "tool.idem": ActionRouteDescriptor("tool.idem", "route-tool-idem", ActionKind.TOOL, PlacementClass.EXTERNAL, EffectSemantics.IDEMPOTENT_EFFECT, "policy-tool-idem"),
    "tool.nonidem": ActionRouteDescriptor("tool.nonidem", "route-tool-nonidem", ActionKind.TOOL, PlacementClass.EXTERNAL, EffectSemantics.NON_IDEMPOTENT_EFFECT, "policy-tool-nonidem"),
    "external.local": ActionRouteDescriptor("external.local", "route-external-local", ActionKind.EXTERNAL_HTTP, PlacementClass.EXTERNAL, EffectSemantics.READ_ONLY, "policy-external-local"),
}


def descriptor(agent_id: int) -> AgentDescriptorV7:
    if agent_id == 1:
        return AgentDescriptorV7(agent_id, ("agent.a",), "publisher-local", 1, PlacementClass.EXTERNAL, None, ("tool.a",), "LOCAL_TEST", EPOCH)
    if agent_id == 2:
        return AgentDescriptorV7(agent_id, ("agent.b",), "publisher-local", 1, PlacementClass.EXTERNAL, None, ("tool.b",), "LOCAL_TEST", EPOCH)
    if agent_id == 3:
        service = AgentServiceRouteDescriptor("route-agent-c", EffectSemantics.READ_ONLY, "policy-agent-c", PlacementClass.EXTERNAL)
        return AgentDescriptorV7(agent_id, ("agent.c",), "publisher-local", 1, PlacementClass.EXTERNAL, service, (), "LOCAL_TEST", EPOCH)
    if agent_id == 10:
        return AgentDescriptorV7(agent_id, ("agent.tools",), "publisher-local", 1, PlacementClass.EXTERNAL, None,
                                 ("tool.read", "tool.idem", "tool.nonidem", "external.local"), "LOCAL_TEST", EPOCH)
    if agent_id in (11, 12, 13):
        semantics = {11: EffectSemantics.READ_ONLY, 12: EffectSemantics.IDEMPOTENT_EFFECT, 13: EffectSemantics.NON_IDEMPOTENT_EFFECT}[agent_id]
        service = AgentServiceRouteDescriptor(f"route-agent-{agent_id}", semantics, f"policy-agent-{agent_id}", PlacementClass.EXTERNAL)
        return AgentDescriptorV7(agent_id, (f"agent.service.{agent_id}",), "publisher-local", 1, PlacementClass.EXTERNAL, service, (), "LOCAL_TEST", EPOCH)
    if agent_id == 21:
        service = AgentServiceRouteDescriptor(
            "route-agent-21",
            EffectSemantics.READ_ONLY,
            "policy-agent-21",
            PlacementClass.EXTERNAL,
        )
        return AgentDescriptorV7(
            agent_id,
            ("agent.workflow.21",),
            "publisher-local",
            1,
            PlacementClass.EXTERNAL,
            service,
            ("tool.read", "tool.idem", "tool.nonidem", "external.local"),
            "LOCAL_TEST",
            EPOCH,
        )
    return AgentDescriptorV7(agent_id, (f"agent.filler.{agent_id}",), "publisher-local", 1, PlacementClass.EXTERNAL,
                             None, (f"tool.filler.{agent_id}",), "LOCAL_TEST", EPOCH)


def build_registry(path: Path, codec: AgentDescriptorV7Codec, count: int = 1000) -> None:
    with path.open("xb") as handle:
        for agent_id in range(count):
            handle.write(codec.encode(descriptor(agent_id)))
    if path.stat().st_size != count * AGENT_DESCRIPTOR_V7_BYTES:
        raise AssertionError("canonical V9 registry size mismatch")


def real_pir_select(output: Path, session_specs: list[CanonicalSessionSpec]) -> dict[str, AgentDescriptorV7]:
    output.mkdir(parents=True, exist_ok=False)
    key = os.urandom(32)
    codec = AgentDescriptorV7Codec(key, EPOCH)
    registry = output / "encrypted_agent_descriptor_v7_rows.bin"
    build_registry(registry, codec)
    requests = [PIRRequest(spec.case_id, index, spec.agent_id, "PRIVATE_AGENT_SELECTION") for index, spec in enumerate(session_specs)]
    artifacts = run_simplepir(ROOT, registry, 1000, requests, output / "simplepir")
    selected: dict[str, AgentDescriptorV7] = {}
    for spec, row in zip(session_specs, artifacts.recovered, strict=True):
        recovered = codec.decode(row, expected_agent_id=spec.agent_id)
        if recovered != descriptor(spec.agent_id):
            raise AssertionError("PIR-selected descriptor semantic mismatch")
        selected[spec.case_id] = recovered
    return selected


class Providers:
    definitions = {
        "route-tool-a": ("TOOL_A", 0, 1, False),
        "route-tool-b": ("TOOL_B", 1, 3, True),
        "route-agent-c": ("AGENT_C", 2, 6, False),
        "route-tool-read": ("TOOL_READ", 0, 2, False),
        "route-tool-idem": ("TOOL_IDEM", 1, 5, True),
        "route-tool-nonidem": ("TOOL_NONIDEM", 2, 8, True),
        "route-external-local": ("EXTERNAL_LOCAL", 0, 4, False),
        "route-agent-11": ("AGENT_READ", 0, 3, False),
        "route-agent-12": ("AGENT_IDEM", 1, 7, True),
        "route-agent-13": ("AGENT_NONIDEM", 3, 12, True),
        "route-agent-21": ("AGENT_WORKFLOW", 0, 3, False),
    }

    def __init__(self, output: Path):
        self.output = output
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.endpoints: dict[str, str] = {}

    def __enter__(self) -> "Providers":
        for index, (route, (name, minimum, maximum, effectful)) in enumerate(self.definitions.items()):
            metrics = self.output / "providers" / f"{route}.json"
            command = [sys.executable, "-m", "canonical_v9.provider_emulator", "--name", name,
                       "--min-delay-ms", str(minimum), "--max-delay-ms", str(maximum),
                       "--metrics", str(metrics), "--seed", str(index + 1)]
            if effectful:
                command.append("--effectful")
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            assert process.stdout is not None
            ready = json.loads(process.stdout.readline())
            if not ready.get("ready"):
                raise RuntimeError(f"provider {route} did not start")
            self.processes[route] = process
            self.endpoints[route] = str(ready["endpoint"])
        return self

    def __exit__(self, *_args: object) -> None:
        for process in self.processes.values():
            process.terminate()
        for process in self.processes.values():
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def go_kind(kind: ActionKind) -> str:
    return {ActionKind.TOOL: "REAL_TOOL", ActionKind.AGENT_SERVICE: "REAL_AGENT_SERVICE", ActionKind.EXTERNAL_HTTP: "REAL_EXTERNAL_HTTP"}[kind]


def route_specs(providers: Providers) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for value in ROUTES.values():
        values.append({"route_handle": value.route_handle, "action_kind": go_kind(value.action_kind),
                       "effect_semantics": value.effect_semantics.value, "endpoint": providers.endpoints[value.route_handle],
                       "policy_id": value.policy_id})
    for agent_id in (3, 11, 12, 13, 21):
        service = descriptor(agent_id).agent_service
        assert service is not None
        values.append({"route_handle": service.route_handle, "action_kind": "REAL_AGENT_SERVICE",
                       "effect_semantics": service.effect_semantics.value, "endpoint": providers.endpoints[service.route_handle],
                       "policy_id": service.policy_id})
    return values


def resolve_session(spec: CanonicalSessionSpec, selected: AgentDescriptorV7) -> list[dict[str, object]]:
    router = TrustedActionRouter(ROUTES)
    resolved = [router.resolve(intent, selected, PrivacyProfile.STRICT) for intent in spec.action_intents]
    return [{"operation_id": item.operation_id, "action_kind": go_kind(item.action_kind),
             "route_handle": item.route_handle, "effect_semantics": item.effect_semantics.value,
             "policy_id": item.policy_id,
             # Go's encoding/json representation for []byte is base64 text.
             "protected_arguments": base64.b64encode(item.protected_arguments).decode("ascii")}
            for item in resolved]


def capacity_profile(actions: int, profile_id: str) -> dict[str, int | str]:
    round_period_ms = 5
    completion_bound_ms = 50
    completion_rounds = (completion_bound_ms + round_period_ms - 1) // round_period_ms
    terminal_rounds = 1
    admission_rounds = actions
    rounds = admission_rounds + completion_rounds + actions + terminal_rounds
    return {"profile_id": profile_id, "rounds": rounds, "admission_rounds": admission_rounds,
            "maximum_real_operations": actions, "round_period_ms": round_period_ms,
            "provider_completion_bound_ms": completion_bound_ms, "request_bhttp_bytes": 1024,
            "response_bhttp_bytes": 768, "request_final_bytes": 1079, "response_final_bytes": 800}


def invoke_go(output: Path, profile_id: str, actions: list[dict[str, object]], providers: Providers) -> dict[str, object]:
    if not GO_RUNNER.is_file():
        raise FileNotFoundError(f"canonical Go runner is missing: {GO_RUNNER}")
    profile = capacity_profile(len(actions), profile_id)
    plan = dict(profile)
    plan.update({"state_directory": str(output / "gateway_state"), "routes": route_specs(providers), "actions": actions})
    plan_path = output / "trusted_plan.json"
    result_path = output / "go_canonical_result.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    completed = subprocess.run([str(GO_RUNNER), "--plan", str(plan_path), "--output", str(result_path)],
                               cwd=ROOT, text=True, capture_output=True)
    (output / "go_stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output / "go_stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"canonical Go runner failed: {completed.stderr}")
    return json.loads(result_path.read_text(encoding="utf-8"))


def invoke_go_diagnostics(plan_path: Path, output: Path) -> dict[str, object]:
    completed = subprocess.run(
        [str(GO_RUNNER), "--plan", str(plan_path), "--output", str(output), "--diagnostics"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"canonical diagnostics failed: {completed.stderr}")
    return json.loads(output.read_text(encoding="utf-8"))


def deliver_results(output: Path, expected: list[str], result: dict[str, object]) -> dict[str, object]:
    ledger = DeliveryLedger(output / "trusted_delivery_ledger.json")
    sink: list[str] = []
    for item in result["results"]:
        operation_id = str(item["operation_id"])
        ledger.record_received(operation_id)
        ledger.mark_decapsulated(operation_id)
        ledger.deliver(operation_id, lambda value=operation_id: sink.append(value))
    replay_suppressed = 0
    if sink:
        operation_id = sink[0]
        ledger.record_received(operation_id)
        ledger.mark_decapsulated(operation_id)
        decision = ledger.deliver(operation_id, lambda: sink.append("UNEXPECTED_REPLAY"))
        replay_suppressed = int(decision.value == "SUPPRESS_ALREADY_DELIVERED")
    return {"expected": expected, "framework_sink": sink, "missing": sorted(set(expected) - set(sink)),
            "unexpected": sorted(set(sink) - set(expected)), "replay_suppressed": replay_suppressed}


def intent(capability: str, kind: ActionKind, operation_id: str) -> ProtectedActionIntent:
    return ProtectedActionIntent(capability, f"synthetic:{operation_id}".encode(), "canonical-v9", operation_id, kind)


def multi_agent_smoke(root: Path) -> list[dict[str, object]]:
    specs = [
        CanonicalSessionSpec("agent-a", "agent.a", 1, (intent("tool.a", ActionKind.TOOL, "smoke-a"),)),
        CanonicalSessionSpec("agent-b", "agent.b", 2, (intent("tool.b", ActionKind.TOOL, "smoke-b"),)),
        CanonicalSessionSpec("agent-c", "agent.c", 3, (intent("agent.c", ActionKind.AGENT_SERVICE, "smoke-c"),)),
    ]
    selected = real_pir_select(root / "pir", specs)
    rows: list[dict[str, object]] = []
    with Providers(root) as providers:
        for spec in specs:
            case = root / spec.case_id
            case.mkdir(parents=True)
            actions = resolve_session(spec, selected[spec.case_id])
            (case / "trusted_selected_agent.json").write_text(
                json.dumps({"selected_agent_id": selected[spec.case_id].agent_id,
                            "descriptor_schema": "AgentDescriptorV7/7", "catalog_epoch": EPOCH,
                            "authenticated_from_real_pir": True}, indent=2) + "\n",
                encoding="utf-8",
            )
            result = invoke_go(case, "V9-SMOKE-CANONICAL", actions, providers)
            delivery = deliver_results(case, [actions[0]["operation_id"]], result)
            passed = delivery["missing"] == [] and delivery["unexpected"] == [] and result["provider_invocations"] == 1
            rows.append({"case_id": spec.case_id, "agent_id": spec.agent_id, "authorized": True,
                         "provider_invocations": result["provider_invocations"], "delivered": len(delivery["framework_sink"]), "passed": passed})
        negative = CanonicalSessionSpec("agent-a-forbidden-b", "agent.a", 1, (intent("tool.b", ActionKind.TOOL, "smoke-deny"),))
        try:
            resolve_session(negative, selected["agent-a"])
            denied = False
        except PermissionError:
            denied = True
        rows.append({"case_id": negative.case_id, "agent_id": 1, "authorized": False,
                     "provider_invocations": 0, "delivered": 0, "passed": denied})
    return rows


def workload(count: int) -> list[CanonicalSessionSpec]:
    families = [
        (10, "agent.tools", "tool.read", ActionKind.TOOL),
        (10, "agent.tools", "tool.idem", ActionKind.TOOL),
        (10, "agent.tools", "tool.nonidem", ActionKind.TOOL),
        (10, "agent.tools", "external.local", ActionKind.EXTERNAL_HTTP),
        (11, "agent.service.11", "agent.service.11", ActionKind.AGENT_SERVICE),
        (12, "agent.service.12", "agent.service.12", ActionKind.AGENT_SERVICE),
        (13, "agent.service.13", "agent.service.13", ActionKind.AGENT_SERVICE),
    ]
    grouped: dict[tuple[int, str], list[ProtectedActionIntent]] = {}
    for index in range(count):
        agent_id, agent_capability, action_capability, kind = families[index % len(families)]
        operation_id = f"functional-{count}-{index:04d}"
        grouped.setdefault((agent_id, agent_capability), []).append(intent(action_capability, kind, operation_id))
    return [CanonicalSessionSpec(f"functional-{count}-agent-{agent_id}", capability, agent_id, tuple(actions))
            for (agent_id, capability), actions in grouped.items()]


def functional_run(count: int, output: Path) -> dict[str, object]:
    specs = workload(count)
    selected = real_pir_select(output / "pir", specs)
    aggregate = {"admitted": 0, "delivered": 0, "missing": 0, "unexpected": 0,
                 "provider_invocations": 0, "dummy_provider_operations": 0,
                 "profile_overflow_events": 0, "unexpected_duplicate_framework_deliveries": 0,
                 "sessions": len(specs)}
    with Providers(output) as providers:
        for spec in specs:
            session_output = output / "sessions" / spec.case_id
            session_output.mkdir(parents=True)
            actions = resolve_session(spec, selected[spec.case_id])
            (session_output / "trusted_selected_agent.json").write_text(
                json.dumps({"selected_agent_id": selected[spec.case_id].agent_id,
                            "descriptor_schema": "AgentDescriptorV7/7", "catalog_epoch": EPOCH,
                            "authenticated_from_real_pir": True,
                            "authorized_operation_ids": [item["operation_id"] for item in actions]}, indent=2) + "\n",
                encoding="utf-8",
            )
            # The public profile names only the development workload and its
            # public admission count. It must never encode the selected Agent.
            result = invoke_go(session_output, f"V9-FUNCTIONAL-{count}-PUBLIC-ACTIONS-{len(actions)}", actions, providers)
            expected = [str(item["operation_id"]) for item in actions]
            delivery = deliver_results(session_output, expected, result)
            (session_output / "delivery_result.json").write_text(json.dumps(delivery, indent=2) + "\n", encoding="utf-8")
            aggregate["admitted"] += len(actions)
            aggregate["delivered"] += len(delivery["framework_sink"])
            aggregate["missing"] += len(delivery["missing"])
            aggregate["unexpected"] += len(delivery["unexpected"])
            aggregate["provider_invocations"] += int(result["provider_invocations"])
            aggregate["dummy_provider_operations"] += int(result["dummy_provider_operations"])
            aggregate["profile_overflow_events"] += int(result["profile_overflow_events"])
            aggregate["unexpected_duplicate_framework_deliveries"] += int("UNEXPECTED_REPLAY" in delivery["framework_sink"])
    aggregate["passed"] = all((aggregate["admitted"] == count, aggregate["delivered"] == count,
                                aggregate["missing"] == 0, aggregate["unexpected"] == 0,
                                aggregate["provider_invocations"] == count,
                                aggregate["dummy_provider_operations"] == 0,
                                aggregate["profile_overflow_events"] == 0,
                                aggregate["unexpected_duplicate_framework_deliveries"] == 0))
    (output / "summary.json").write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
    return aggregate


def import_audit() -> dict[str, object]:
    paths = [ROOT / "canonical_v9", ROOT / "common_action_gateway_v2" / "canonicalv9",
             ROOT / "common_action_gateway_v2" / "cmd" / "canonical-v9-runner"]
    # Assemble these strings so the audit implementation does not match its own
    # deny-list literals.  The resulting values are still the exact forbidden
    # legacy symbols searched in canonical source files.
    forbidden = (
        "Envelope" + "Codec",
        "Provider" + "Fast",
        "Provider" + "Slow",
        "LEGACY_DEV_" + "TRANSPORT",
        "EncodeRequest(" + "aead",
    )
    findings: list[dict[str, str]] = []
    for base in paths:
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".go"}:
                text = path.read_text(encoding="utf-8")
                for token in forbidden:
                    if token in text:
                        findings.append({"path": str(path.relative_to(ROOT)), "token": token})
    return {"status": "PASS" if not findings else "FAIL", "findings": findings,
            "audited_paths": [str(path.relative_to(ROOT)) for path in paths]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ROOT / "results_v9" / "canonical_functional")
    args = parser.parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"refusing to overwrite canonical run {args.output_root}")
    args.output_root.mkdir(parents=True)
    audit = import_audit()
    (args.output_root / "import_dependency_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    if audit["status"] != "PASS":
        raise AssertionError(f"legacy dependency entered canonical runner: {audit['findings']}")
    smoke_rows = multi_agent_smoke(args.output_root / "multi_agent_smoke")
    with (args.output_root / "multi_agent_smoke.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(smoke_rows[0]))
        writer.writeheader()
        writer.writerows(smoke_rows)
    required_smoke = ROOT / "CANONICAL_MULTI_AGENT_SMOKE_V9.csv"
    if required_smoke.exists():
        raise FileExistsError(f"refusing to overwrite {required_smoke}")
    with required_smoke.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(smoke_rows[0]))
        writer.writeheader()
        writer.writerows(smoke_rows)

    diagnostic_path = args.output_root / "canonical_diagnostics.json"
    diagnostics = invoke_go_diagnostics(
        args.output_root / "multi_agent_smoke" / "agent-a" / "trusted_plan.json",
        diagnostic_path,
    )
    size_csv = ROOT / "CANONICAL_OHTTP_SIZE_MATRIX_V9.csv"
    if size_csv.exists():
        raise FileExistsError(f"refusing to overwrite {size_csv}")
    with size_csv.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(diagnostics["size_matrix"][0]))
        writer.writeheader()
        writer.writerows(diagnostics["size_matrix"])

    profiles = {str(count): capacity_profile(count, f"V9-FUNCTIONAL-{count}") for count in (1, 10, 50, 100)}
    profile_path = ROOT / "FUNCTIONAL_DEVELOPMENT_PROFILES_V9.json"
    if profile_path.exists():
        raise FileExistsError(f"refusing to overwrite {profile_path}")
    profile_path.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")
    functional = {}
    for count in (1, 10, 50, 100):
        run_dir = ROOT / f"CANONICAL_FUNCTIONAL_{count}_V9"
        if run_dir.exists():
            raise FileExistsError(f"refusing to overwrite canonical run {run_dir}")
        run_dir.mkdir(parents=True)
        functional[str(count)] = functional_run(count, run_dir)
    (args.output_root / "functional_summary.json").write_text(json.dumps(functional, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"smoke": smoke_rows, "diagnostics": diagnostics, "functional": functional}, indent=2))


if __name__ == "__main__":
    main()

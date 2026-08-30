from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Mapping

from action_privacy_v8 import (
    AgentDescriptorV7,
    AgentDescriptorV7Codec,
    DeliveryLedger,
    PrivacyProfile,
    ProtectedActionIntent,
    TrustedActionRouter,
)
from action_privacy_v8.descriptor import AGENT_DESCRIPTOR_V7_BYTES
from canonical_v9.runner import (
    EPOCH,
    ROUTES,
    descriptor,
    go_kind,
    resolve_session,
    route_specs,
    CanonicalSessionSpec,
)
from canonical_v9_1.projection import strict_size_projection, strict_structural_projection
from cryptographic_closure.pir_backend import SIMPLEPIR_COMMIT
from v10_holdout.harness import load_v10_profile
from v11_full_scope.action_model import protected_payload
from v11_full_scope.canonical import (
    LocalTrustedBackendV11,
    V11EvidenceProviders,
    _canonical_ids,
    internal_descriptor,
)
from v11_full_scope.models import V11ActionCase, V11ActionOutcome
from v11_3.profile import OnlinePublicProfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNNER = ROOT / "common_action_gateway_v2" / "bin" / "canonical-v11_2-runner"
if os.name == "nt":
    DEFAULT_RUNNER = DEFAULT_RUNNER.with_suffix(".exe")


class OnlineSessionFailure(RuntimeError):
    pass


class OnlineSimplePIRResolver:
    """Persistent official SimplePIR setup with indices supplied only online."""

    def __init__(self, output: Path, *, record_count: int = 1000):
        self.output = output.resolve()
        if record_count < 64:
            raise ValueError("online SimplePIR development catalog must contain at least 64 rows")
        self.record_count = record_count
        self.process: subprocess.Popen[str] | None = None
        self.codec: AgentDescriptorV7Codec | None = None
        self.stderr_lines: list[str] = []
        self.stderr_thread: threading.Thread | None = None
        self.query_count = 0
        self.query_hashes: list[str] = []
        self.prebuilt_bridge_used = False
        self.query_lock = threading.Lock()

    def __enter__(self) -> "OnlineSimplePIRResolver":
        self.output.mkdir(parents=True, exist_ok=False)
        key = os.urandom(32)
        self.codec = AgentDescriptorV7Codec(key, EPOCH)
        registry = self.output / "encrypted_agent_descriptor_v7_rows.bin"
        # The dynamic catalog contains both external Agents and the development
        # local-trusted Agent. No future query index is passed to preprocessing.
        with registry.open("xb") as handle:
            for agent_id in range(self.record_count):
                value = internal_descriptor(agent_id) if agent_id == 20 else descriptor(agent_id)
                handle.write(self.codec.encode(value))
        if registry.stat().st_size != self.record_count * AGENT_DESCRIPTOR_V7_BYTES:
            raise AssertionError("online SimplePIR registry size mismatch")

        bridge = ROOT / "pir_integration" / "simplepir_bridge"
        env = dict(os.environ)
        prebuilt_bridge = bridge / (
            "acv-simplepir-online.exe" if os.name == "nt" else "acv-simplepir-online"
        )
        self.prebuilt_bridge_used = prebuilt_bridge.is_file()
        if self.prebuilt_bridge_used:
            # A verified prebuilt CGO binary is self-contained with respect to
            # the Go compiler and C compiler.  Toolchain discovery belongs to
            # the build path and must not gate or silently alter execution.
            command = [str(prebuilt_bridge), "--interactive"]
        elif os.name == "nt":
            # Retained solely for Windows development fixtures.  Linux/V12
            # execution fails closed rather than silently changing to go run.
            go = ROOT / ".toolchains" / "go" / "Go" / "bin" / "go.exe"
            gcc_dir = ROOT / ".toolchains" / "winlibs" / "mingw64" / "bin"
            if not go.is_file() or not (gcc_dir / "gcc.exe").is_file():
                raise FileNotFoundError("online SimplePIR prebuilt bridge is unavailable")
            env["PATH"] = str(go.parent) + os.pathsep + str(gcc_dir) + os.pathsep + env.get("PATH", "")
            env["CC"] = str(gcc_dir / "gcc.exe")
            env["CGO_ENABLED"] = "1"
            command = [str(go), "run", ".", "--interactive"]
        else:
            raise FileNotFoundError(
                "online SimplePIR requires the frozen prebuilt bridge; source fallback is disabled"
            )
        command.extend([
            "--database", str(registry), "--records", str(self.record_count),
            "--client-trace", str(self.output / "client_private_trace.jsonl"),
            "--server-trace", str(self.output / "server_visible_trace.jsonl"),
            "--commit", SIMPLEPIR_COMMIT,
        ])
        self.process = subprocess.Popen(
            command, cwd=bridge, env=env, text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=1,
        )
        assert self.process.stdout is not None and self.process.stderr is not None
        startup_lines: list[str] = []
        ready: dict[str, Any] | None = None
        for ready_line in self.process.stdout:
            startup_lines.append(ready_line)
            try:
                candidate = json.loads(ready_line)
            except json.JSONDecodeError:
                continue
            if candidate.get("type") == "PIR_READY":
                ready = candidate
                break
        if ready is None:
            raise RuntimeError("online SimplePIR exited before PIR_READY: " + self.process.stderr.read())
        if ready != {
            "future_indices_received": 0,
            "records": self.record_count,
            "type": "PIR_READY",
        }:
            raise AssertionError(f"unexpected online SimplePIR readiness record: {ready}")
        self.stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self.stderr_thread.start()
        (self.output / "preprocessing_ready.json").write_text(
            json.dumps({**ready, "official_commit": SIMPLEPIR_COMMIT}, indent=2) + "\n",
            encoding="utf-8",
        )
        (self.output / "preprocessing_stdout.txt").write_text("".join(startup_lines), encoding="utf-8")
        return self

    def _drain_stderr(self) -> None:
        assert self.process is not None and self.process.stderr is not None
        self.stderr_lines.extend(self.process.stderr)

    def query(self, operation_id: str, index: int) -> AgentDescriptorV7:
        with self.query_lock:
            if self.process is None or self.codec is None or self.process.stdin is None or self.process.stdout is None:
                raise RuntimeError("online SimplePIR is not active")
            self.process.stdin.write(json.dumps({"operation_id": operation_id, "index": index}) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("online SimplePIR closed during query")
            response = json.loads(line)
        if response.get("type") != "PIR_RESULT" or response.get("operation_id") != operation_id or not response.get("correct"):
            raise RuntimeError(f"online SimplePIR query failed: {response}")
        row = base64.b64decode(response["record_base64"])
        recovered = self.codec.decode(row, expected_agent_id=index)
        expected = internal_descriptor(index) if index == 20 else descriptor(index)
        if recovered != expected:
            raise AssertionError("online PIR-selected descriptor semantic mismatch")
        self.query_count += 1
        self.query_hashes.append(str(response["query_sha256"]))
        return recovered

    def __exit__(self, *_args: object) -> None:
        if self.process is None:
            return
        try:
            if self.process.stdin is not None and not self.process.stdin.closed:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            if self.stderr_thread is not None:
                self.stderr_thread.join(timeout=2)
            (self.output / "bridge_stderr.txt").write_text("".join(self.stderr_lines), encoding="utf-8")
            (self.output / "online_query_summary.json").write_text(
                json.dumps(
                    {
                        "official_simplepir": True,
                        "commit": SIMPLEPIR_COMMIT,
                        "query_count": self.query_count,
                        "fresh_query_hashes": len(self.query_hashes) == len(set(self.query_hashes)),
                        "future_indices_in_startup": 0,
                        "prebuilt_bridge_binary": self.prebuilt_bridge_used,
                        "record_count": self.record_count,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        finally:
            # Popen does not close PIPE file objects merely because the child
            # exited.  Release every descriptor even when shutdown or evidence
            # serialization fails.
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
            self.process = None


class CanonicalOnlineSession:
    """One long-lived public session shared by an entire framework run."""

    def __init__(
        self,
        output: Path,
        cases: list[V11ActionCase],
        *,
        runner_binary: Path | None = None,
        plan_overrides: Mapping[str, object] | None = None,
        public_profile: OnlinePublicProfile | None = None,
        pir_delay_ms: int = 0,
        decision_delay_ms: int = 0,
        pir_record_count: int = 1000,
    ):
        self.output = output
        self.cases = {case.operation_id: case for case in cases}
        if len(self.cases) != len(cases):
            raise ValueError("online trajectory operation IDs must be unique")
        self.runner_binary = runner_binary or DEFAULT_RUNNER
        self.plan_overrides = dict(plan_overrides or {})
        self.public_profile = public_profile
        self.pir_delay_ms = pir_delay_ms
        self.decision_delay_ms = decision_delay_ms
        self.pir_record_count = pir_record_count
        if pir_delay_ms < 0 or decision_delay_ms < 0:
            raise ValueError("private development delays cannot be negative")
        self.providers: V11EvidenceProviders | None = None
        self.pir: OnlineSimplePIRResolver | None = None
        self.process: subprocess.Popen[str] | None = None
        self.reader_thread: threading.Thread | None = None
        self.pir_query_count = 0
        self.pir_query_hashes: tuple[str, ...] = ()
        self.events: list[dict[str, Any]] = []
        self.lifecycle: list[dict[str, Any]] = []
        self.condition = threading.Condition()
        self.results: dict[str, dict[str, Any]] = {}
        self.failures: dict[str, str] = {}
        self.session_failure: str | None = None
        self.trace: dict[str, Any] | None = None
        self._ledger: DeliveryLedger | None = None
        self._delivery_lock = threading.Lock()
        self._started_ns = 0

    def __enter__(self) -> "CanonicalOnlineSession":
        if self.output.exists():
            raise FileExistsError(f"refusing to overwrite online evidence: {self.output}")
        self.output.mkdir(parents=True)
        if not self.runner_binary.is_file():
            raise FileNotFoundError(f"V11.2 online runner is missing: {self.runner_binary}")
        self.providers = V11EvidenceProviders(
            self.cases, self.output / "private_provider_evidence.json"
        )
        self.pir = OnlineSimplePIRResolver(
            self.output / "pir", record_count=self.pir_record_count
        )
        try:
            self.providers.__enter__()
            self.pir.__enter__()
            profile = self.public_profile or load_v10_profile()
            plan = profile.go_plan_fields()
            plan.update(
                {
                    "profile_id": profile.profile_id
                    if self.public_profile is not None
                    else "V11_2-DEV-H50-ONLINE-P5",
                    "state_directory": str(self.output / "gateway_state"),
                    "routes": route_specs(self.providers),
                    "actions": [],
                    # Qualification profiles own the public slot period.  The old
                    # unconditional value of 5 ms made a non-5-ms profile only a
                    # label change and invalidated scheduler qualification.
                    "round_period_ms": profile.round_period_ms
                    if self.public_profile is not None
                    else 5,
                    "scheduler_tolerance_ms": 3,
                    "preparation_lead_ms": 1,
                }
            )
            allowed = {
                "fault_scheduler_stall_slot",
                "fault_scheduler_stall_ms",
                "fault_delay_response_slot",
                "fault_delay_response_ms",
            }
            unknown = set(self.plan_overrides) - allowed
            if unknown:
                raise ValueError(f"unsupported online development override: {sorted(unknown)}")
            plan.update(self.plan_overrides)
            (self.output / "trusted_online_startup_plan.json").write_text(
                json.dumps(plan, indent=2) + "\n", encoding="utf-8"
            )
            if plan["actions"]:
                raise AssertionError("online startup plan contains future actions")
            result_path = self.output / "go_online_result.json"
            self.process = subprocess.Popen(
                [
                    str(self.runner_binary),
                    "--online",
                    "--plan",
                    str(self.output / "trusted_online_startup_plan.json"),
                    "--output",
                    str(result_path),
                ],
                cwd=ROOT,
                text=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
            )
            self._started_ns = time.monotonic_ns()
            self._ledger = DeliveryLedger(self.output / "trusted_delivery_ledger.json")
            self.reader_thread = threading.Thread(target=self._read_events, daemon=True)
            self.reader_thread.start()
            self._wait(lambda: any(event.get("type") == "SESSION_READY" for event in self.events), timeout=10)
            self._record("SESSION_T0")
            return self
        except BaseException:
            self._release_resources(suppress_errors=True)
            raise

    def _read_events(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        for line in self.process.stdout:
            event = json.loads(line)
            with self.condition:
                self.events.append(event)
                if event.get("type") == "RESULT_AVAILABLE":
                    self.results[str(event["operation_id"])] = event
                elif event.get("type") == "ACTION_REJECTED":
                    self.failures[str(event.get("operation_id", ""))] = str(event.get("reason", "ACTION_REJECTED"))
                elif event.get("type") == "SESSION_FAILURE":
                    self.session_failure = str(event.get("reason", "SESSION_FAILURE"))
                elif event.get("type") == "SESSION_COMPLETE":
                    # A subsequent submit is an explicit closed-admission
                    # outcome, never a new public session.
                    self.session_failure = "SESSION_PUBLIC_SCHEDULE_COMPLETE"
                self.condition.notify_all()

    def _wait(self, predicate, *, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        with self.condition:
            while not predicate():
                if self.session_failure is not None:
                    raise OnlineSessionFailure(self.session_failure)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("trusted online control response timed out")
                self.condition.wait(remaining)

    def _record(self, stage: str, operation_id: str = "", **extra: Any) -> None:
        self.lifecycle.append(
            {
                "stage": stage,
                "operation_id": operation_id,
                "monotonic_ns": time.monotonic_ns(),
                **extra,
            }
        )

    def submit(self, case: V11ActionCase, arguments: dict[str, Any]) -> V11ActionOutcome:
        case.validate()
        if arguments != case.argument_schema.validate_values(case.arguments):
            raise AssertionError("framework changed online structured arguments")
        if case.operation_id not in self.cases:
            raise ValueError("case was not registered with the online development session")
        if self.decision_delay_ms and any(
            item["stage"] == "FRAMEWORK_RESULT_DELIVERED" for item in self.lifecycle
        ):
            time.sleep(self.decision_delay_ms / 1000)
        self._record("ACTION_INTENT_SUBMITTED", case.operation_id)
        assert self.pir is not None
        agent_id, agent_capability, capability, kind = _canonical_ids(case)
        if self.pir_delay_ms:
            time.sleep(self.pir_delay_ms / 1000)
        selected = self.pir.query(case.operation_id, agent_id)
        self._record("DYNAMIC_PIR_DESCRIPTOR_RECOVERED", case.operation_id, agent_id=agent_id)
        protected = ProtectedActionIntent(
            capability,
            protected_payload(case),
            "v11-2-online-development",
            case.operation_id,
            kind,
        )
        if case.placement == "TRUSTED_MODULE_LOCAL":
            resolved = TrustedActionRouter({}).resolve(protected, selected, PrivacyProfile.STRICT)
            if resolved.placement.value != "TRUSTED_MODULE_LOCAL":
                raise AssertionError("dynamic internal Agent resolved outside trusted module")
            self._record("ACTION_ADMITTED", case.operation_id, placement="TRUSTED_MODULE_LOCAL")
            outcome = LocalTrustedBackendV11().execute_internal(case)
            assert self._ledger is not None
            with self._delivery_lock:
                self._ledger.record_received(case.operation_id)
                self._ledger.mark_decapsulated(case.operation_id)
                sink: list[str] = []
                self._ledger.deliver(case.operation_id, lambda: sink.append(outcome.result))
            self._record("FRAMEWORK_RESULT_DELIVERED", case.operation_id, placement="TRUSTED_MODULE_LOCAL")
            return outcome

        session = CanonicalSessionSpec(case.case_id, agent_capability, agent_id, (protected,))
        resolved_actions = resolve_session(session, selected)
        action = resolved_actions[0]
        if action["effect_semantics"] != case.effect_semantics:
            raise AssertionError("dynamic trusted route changed effect semantics")
        assert self.process is not None and self.process.stdin is not None
        try:
            self.process.stdin.write(json.dumps({"type": "SUBMIT_RESOLVED_ACTION", "action": action}) + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise OnlineSessionFailure("PROFILE_ADMISSION_CLOSED") from exc
        self._wait(
            lambda: case.operation_id in self.results or case.operation_id in self.failures,
            timeout=10,
        )
        if case.operation_id in self.failures:
            raise OnlineSessionFailure(self.failures[case.operation_id])
        event = self.results[case.operation_id]
        item = event["result"]
        status = int(item["status"])
        payload = base64.b64decode(item.get("payload") or "").decode("utf-8", errors="replace")
        if case.scenario == "SUCCESS" and status == 2:
            semantics = f"{case.effect_semantics}:SUCCESS"
            result = payload
        elif case.scenario in {"BOUNDED_TIMEOUT", "AMBIGUOUS_RESTART"} and case.effect_semantics == "NON_IDEMPOTENT_EFFECT":
            semantics, result = "NON_IDEMPOTENT_EFFECT:EFFECT_OUTCOME_UNKNOWN", ""
        elif case.scenario == "BOUNDED_TIMEOUT":
            semantics, result = f"{case.effect_semantics}:BOUNDED_TIMEOUT", ""
        else:
            semantics, result = f"{case.effect_semantics}:ERROR", ""
        assert self._ledger is not None and self.providers is not None
        with self._delivery_lock:
            self._ledger.record_received(case.operation_id)
            self._ledger.mark_decapsulated(case.operation_id)
            sink: list[str] = []
            self._ledger.deliver(case.operation_id, lambda: sink.append(result))
        observation = self.providers.observed(case.operation_id)
        self._record("FRAMEWORK_RESULT_DELIVERED", case.operation_id, result_round=int(event.get("round", 0)))
        return V11ActionOutcome(
            result,
            int(case.operation_id in self.providers.effects),
            semantics,
            observation.logical_request,
            {
                "canonical": True,
                "official_simplepir": True,
                "dynamic_agent_resolution": True,
                "descriptor_authenticated": True,
                "one_online_session": True,
                "result_round": int(event.get("round", 0)),
            },
        )

    def implementation(self):
        return lambda case, arguments: self.submit(case, arguments)

    def close(self) -> dict[str, Any]:
        if self.process is None:
            raise RuntimeError("online session was not started")
        if self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            return_code = self.process.wait(timeout=15)
        except subprocess.TimeoutExpired as exc:
            self.process.kill()
            self.process.wait(timeout=5)
            raise OnlineSessionFailure("online runner did not stop at public session end") from exc
        if self.reader_thread is not None:
            self.reader_thread.join(timeout=2)
        stderr = self.process.stderr.read() if self.process.stderr is not None else ""
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
        (self.output / "go_stderr.txt").write_text(stderr, encoding="utf-8")
        (self.output / "trusted_control_events.jsonl").write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in self.events),
            encoding="utf-8",
        )
        (self.output / "private_trajectory.json").write_text(
            json.dumps(self.lifecycle, indent=2) + "\n", encoding="utf-8"
        )
        if return_code != 0:
            raise OnlineSessionFailure(f"online runner failed: {stderr}")
        self.trace = json.loads((self.output / "go_online_result.json").read_text(encoding="utf-8"))
        return self.trace

    def _release_resources(self, *, suppress_errors: bool) -> None:
        errors: list[BaseException] = []
        if self.process is not None:
            try:
                if self.trace is None:
                    self.close()
            except BaseException as value:
                errors.append(value)
            finally:
                for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                    if stream is not None and not stream.closed:
                        stream.close()
                if self.process.poll() is None:
                    self.process.kill()
                    self.process.wait(timeout=5)
                self.process = None
        if self.pir is not None:
            try:
                self.pir_query_count = self.pir.query_count
                self.pir_query_hashes = tuple(self.pir.query_hashes)
                self.pir.__exit__()
            except BaseException as value:
                errors.append(value)
            finally:
                self.pir = None
        if self.providers is not None:
            try:
                self.providers.__exit__()
            except BaseException as value:
                errors.append(value)
            finally:
                self.providers = None
        if errors and not suppress_errors:
            raise errors[0]

    def __exit__(self, exc_type, exc, _traceback) -> None:
        self._release_resources(suppress_errors=exc is not None)

    def public_projections(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if self.trace is None:
            raise RuntimeError("online session has not completed")
        profile = self.public_profile or load_v10_profile()
        return strict_structural_projection(self.trace, profile), strict_size_projection(self.trace, profile)

    def causal_proof(self) -> dict[str, Any]:
        submitted = {item["operation_id"]: item["monotonic_ns"] for item in self.lifecycle if item["stage"] == "ACTION_INTENT_SUBMITTED"}
        delivered = {item["operation_id"]: item["monotonic_ns"] for item in self.lifecycle if item["stage"] == "FRAMEWORK_RESULT_DELIVERED"}
        ids = [case.operation_id for case in self.cases.values()]
        checks = []
        for parent, child in zip(ids, ids[1:]):
            checks.append(
                {
                    "parent": parent,
                    "child": child,
                    "child_submitted_after_parent_delivery": submitted.get(child, 0) > delivered.get(parent, 2**63),
                }
            )
        return {
            "startup_action_count": 0,
            "pre_t0_action_queue_count": 0,
            "checks": checks,
            "passed": all(item["child_submitted_after_parent_delivery"] for item in checks),
        }

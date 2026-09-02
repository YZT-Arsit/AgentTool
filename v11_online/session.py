from __future__ import annotations

import base64
import json
import os
import queue
import subprocess
import threading
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from action_privacy_v8 import (
    AgentDescriptorV7,
    AgentDescriptorV7Codec,
    DeliveryLedger,
    PlacementClass,
    PrivacyProfile,
    ProtectedActionIntent,
    TrustedActionRouter,
)
from action_privacy_v8.descriptor import AGENT_DESCRIPTOR_V7_BYTES
from canonical_v9.runner import (
    EPOCH,
    CanonicalSessionSpec,
    descriptor,
    resolve_session,
    route_specs,
)
from canonical_v9_1.projection import (
    strict_size_projection,
    strict_structural_projection,
)
from cryptographic_closure.pir_backend import SIMPLEPIR_COMMIT
from v10_holdout.harness import load_v10_profile
from v11_3.profile import OnlinePublicProfile
from v11_full_scope.action_model import protected_payload
from v11_full_scope.canonical import (
    LocalTrustedBackendV11,
    V11EvidenceProviders,
    _canonical_ids,
    internal_descriptor,
)
from v11_full_scope.models import V11ActionCase, V11ActionOutcome

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNNER = ROOT / "common_action_gateway_v2" / "bin" / "canonical-v11_2-runner"
TIMING_RUNNER = (
    ROOT / "common_action_gateway_v2" / "bin" / "canonical-v12-timing-runner"
)
CAUSAL_HORIZON_RUNNER = (
    ROOT / "common_action_gateway_v2" / "bin" / "canonical-v12-causal-horizon-runner"
)
DELTA_FUNCTIONAL_RUNNER = (
    ROOT / "common_action_gateway_v2" / "bin" / "canonical-v12-delta-functional-runner"
)
DUPLEX_TIMING_RUNNER = (
    ROOT / "common_action_gateway_v2" / "bin" / "canonical-v12-duplex-timing-runner"
)
TIMING_PIR_BRIDGE = (
    ROOT / "pir_integration" / "simplepir_bridge" / "acv-simplepir-v12-timing"
)
if os.name == "nt":
    DEFAULT_RUNNER = DEFAULT_RUNNER.with_suffix(".exe")
    TIMING_RUNNER = TIMING_RUNNER.with_suffix(".exe")
    CAUSAL_HORIZON_RUNNER = CAUSAL_HORIZON_RUNNER.with_suffix(".exe")
    DELTA_FUNCTIONAL_RUNNER = DELTA_FUNCTIONAL_RUNNER.with_suffix(".exe")
    DUPLEX_TIMING_RUNNER = DUPLEX_TIMING_RUNNER.with_suffix(".exe")
    TIMING_PIR_BRIDGE = TIMING_PIR_BRIDGE.with_suffix(".exe")


class OnlineSessionFailure(RuntimeError):
    pass


class _PIRPreparationDeferred(RuntimeError):
    pass


@dataclass
class _PendingPIRResolution:
    operation_id: str
    index: int
    enqueued_ns: int = field(default_factory=time.monotonic_ns)
    ready: threading.Event = field(default_factory=threading.Event)
    result: AgentDescriptorV7 | None = None
    error: BaseException | None = None


@dataclass
class _SubmittedPIRQuery:
    operation_id: str
    index: int
    pending: _PendingPIRResolution | None
    event: dict[str, Any]
    send_monotonic_ns: int


def duplex_pir_opportunity_times(
    *,
    origin_ns: int,
    ordinal: int,
    period_ns: int,
    initial_lead_ns: int,
    commitment_lead_ns: int,
    previous_public_send_ns: int,
) -> tuple[int, int, int]:
    """Return nominal, eligible, and commitment times from public state only."""

    if ordinal < 0 or period_ns <= 0 or not 0 < commitment_lead_ns < period_ns:
        raise ValueError("invalid duplex PIR public-clock inputs")
    nominal_ns = origin_ns + initial_lead_ns + ordinal * period_ns
    eligible_ns = max(
        nominal_ns,
        previous_public_send_ns + period_ns if ordinal else nominal_ns,
    )
    return nominal_ns, eligible_ns, eligible_ns - commitment_lead_ns


class OnlineSimplePIRResolver:
    """Persistent official SimplePIR setup with indices supplied only online."""

    def __init__(
        self,
        output: Path,
        *,
        record_count: int = 1000,
        bridge_binary: Path | None = None,
    ):
        self.output = output.resolve()
        if record_count < 64:
            raise ValueError(
                "online SimplePIR development catalog must contain at least 64 rows"
            )
        self.record_count = record_count
        self.bridge_binary = (
            bridge_binary.resolve() if bridge_binary is not None else None
        )
        self.process: subprocess.Popen[str] | None = None
        self.codec: AgentDescriptorV7Codec | None = None
        self.stderr_lines: list[str] = []
        self.stderr_thread: threading.Thread | None = None
        self.query_count = 0
        self.query_hashes: list[str] = []
        self.prebuilt_bridge_used = False
        self.query_lock = threading.Lock()
        self.response_queue: queue.Queue[str | BaseException] = queue.Queue()
        self.stdout_thread: threading.Thread | None = None
        self.cover_condition = threading.Condition()
        self.cover_pending: deque[_PendingPIRResolution] = deque()
        self.cover_thread: threading.Thread | None = None
        self.cover_complete = False
        self.cover_error: BaseException | None = None
        self.cover_opportunities = 0
        self.cover_period_ms = 0
        self.cover_dummy_index = 999
        self.cover_initial_lead_ms = 25
        self.cover_liveness_cap_ms = 60_000
        self.cover_origin_ns = 0
        self.query_completion_bound_ms = 0
        self.real_query_count = 0
        self.dummy_query_count = 0
        self.descriptor_cache: dict[tuple[int, int], AgentDescriptorV7] = {}
        self.descriptor_cache_lock = threading.Lock()
        self.descriptor_cache_hits = 0
        self.descriptor_cache_misses = 0
        self.descriptor_cache_events: list[dict[str, Any]] = []
        self.cover_events: list[dict[str, Any]] = []
        self.pir_commitment_lead_ms = 0
        self.registry_answer_release_delay_ms = 0
        self.registry_worker_lanes = 0
        self.registry_max_inflight = 0
        self.completion_queue: queue.Queue[_SubmittedPIRQuery | None] | None = None
        self.completion_thread: threading.Thread | None = None

    @staticmethod
    def _dummy_descriptor(agent_id: int) -> AgentDescriptorV7:
        return AgentDescriptorV7(
            agent_id=agent_id,
            capability_ids=("agent.cover.noop",),
            publisher_key_id="publisher-local",
            agent_version=1,
            placement=PlacementClass.EXTERNAL,
            agent_service=None,
            allowed_tool_capabilities=(),
            trust_class="AUTHENTICATED_COVER_NOOP",
            catalog_epoch=EPOCH,
        ).validated()

    def __enter__(self) -> OnlineSimplePIRResolver:
        self.output.mkdir(parents=True, exist_ok=False)
        key = os.urandom(32)
        self.codec = AgentDescriptorV7Codec(key, EPOCH)
        registry = self.output / "encrypted_agent_descriptor_v7_rows.bin"
        # The dynamic catalog contains both external Agents and the development
        # local-trusted Agent. No future query index is passed to preprocessing.
        with registry.open("xb") as handle:
            for agent_id in range(self.record_count):
                if agent_id == self.cover_dummy_index:
                    value = self._dummy_descriptor(agent_id)
                else:
                    value = (
                        internal_descriptor(agent_id)
                        if agent_id == 20
                        else descriptor(agent_id)
                    )
                handle.write(self.codec.encode(value))
        if registry.stat().st_size != self.record_count * AGENT_DESCRIPTOR_V7_BYTES:
            raise AssertionError("online SimplePIR registry size mismatch")

        bridge = ROOT / "pir_integration" / "simplepir_bridge"
        env = dict(os.environ)
        prebuilt_bridge = self.bridge_binary or bridge / (
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
                raise FileNotFoundError(
                    "online SimplePIR prebuilt bridge is unavailable"
                )
            env["PATH"] = (
                str(go.parent)
                + os.pathsep
                + str(gcc_dir)
                + os.pathsep
                + env.get("PATH", "")
            )
            env["CC"] = str(gcc_dir / "gcc.exe")
            env["CGO_ENABLED"] = "1"
            command = [str(go), "run", ".", "--interactive"]
        else:
            raise FileNotFoundError(
                "online SimplePIR requires the frozen prebuilt bridge; source fallback is disabled"
            )
        command.extend(
            [
                "--database",
                str(registry),
                "--records",
                str(self.record_count),
                "--client-trace",
                str(self.output / "client_private_trace.jsonl"),
                "--server-trace",
                str(self.output / "server_visible_trace.jsonl"),
                "--commit",
                SIMPLEPIR_COMMIT,
            ]
        )
        self.process = subprocess.Popen(
            command,
            cwd=bridge,
            env=env,
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
            raise RuntimeError(
                "online SimplePIR exited before PIR_READY: "
                + self.process.stderr.read()
            )
        expected_ready = {
            "future_indices_received": 0,
            "records": self.record_count,
            "type": "PIR_READY",
        }
        if (
            any(ready.get(key) != value for key, value in expected_ready.items())
            or ready.get("prebuilt_public_cover_queries") not in (None, 100)
            or set(ready) - {*expected_ready, "prebuilt_public_cover_queries"}
        ):
            raise AssertionError(
                f"unexpected online SimplePIR readiness record: {ready}"
            )
        self.stdout_thread = threading.Thread(target=self._drain_stdout, daemon=True)
        self.stdout_thread.start()
        self.stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self.stderr_thread.start()
        (self.output / "preprocessing_ready.json").write_text(
            json.dumps({**ready, "official_commit": SIMPLEPIR_COMMIT}, indent=2) + "\n",
            encoding="utf-8",
        )
        (self.output / "preprocessing_stdout.txt").write_text(
            "".join(startup_lines), encoding="utf-8"
        )
        return self

    def _drain_stderr(self) -> None:
        assert self.process is not None and self.process.stderr is not None
        self.stderr_lines.extend(self.process.stderr)

    def _drain_stdout(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        try:
            for line in self.process.stdout:
                self.response_queue.put(line)
        except BaseException as exc:
            self.response_queue.put(exc)
        finally:
            self.response_queue.put(
                RuntimeError("online SimplePIR response stream closed")
            )

    def _decode_query_response(
        self, operation_id: str, index: int, response_item: str | BaseException
    ) -> AgentDescriptorV7:
        if isinstance(response_item, BaseException):
            raise response_item
        response = json.loads(response_item)
        if (
            response.get("type") == "PIR_DEFERRED"
            and response.get("operation_id") == operation_id
        ):
            self.query_count += 1
            if response.get("query_sha256"):
                self.query_hashes.append(str(response["query_sha256"]))
            raise _PIRPreparationDeferred(
                "real PIR preparation missed an expired public opportunity"
            )
        if (
            response.get("type") != "PIR_RESULT"
            or response.get("operation_id") != operation_id
            or not response.get("correct")
        ):
            raise RuntimeError(f"online SimplePIR query failed: {response}")
        assert self.codec is not None
        row = base64.b64decode(response["record_base64"])
        recovered = self.codec.decode(row, expected_agent_id=index)
        if index == self.cover_dummy_index:
            expected = self._dummy_descriptor(index)
        else:
            expected = internal_descriptor(index) if index == 20 else descriptor(index)
        if recovered != expected:
            raise AssertionError("online PIR-selected descriptor semantic mismatch")
        self.query_count += 1
        self.query_hashes.append(str(response["query_sha256"]))
        return recovered

    def _await_response(
        self,
        operation_id: str,
        index: int,
        send_ns: int,
        *,
        timeout_ms: int | None = None,
    ) -> AgentDescriptorV7:
        try:
            effective_timeout_ms = (
                self.query_completion_bound_ms if timeout_ms is None else timeout_ms
            )
            if effective_timeout_ms:
                elapsed = max(0, time.monotonic_ns() - send_ns)
                remaining = effective_timeout_ms / 1000 - elapsed / 1_000_000_000
                if remaining <= 0:
                    raise queue.Empty
                response_item = self.response_queue.get(timeout=remaining)
            else:
                response_item = self.response_queue.get()
        except queue.Empty as exc:
            raise TimeoutError(
                f"online SimplePIR query exceeded {self.query_completion_bound_ms} ms completion bound"
            ) from exc
        return self._decode_query_response(operation_id, index, response_item)

    def _submit_query(
        self,
        operation_id: str,
        index: int,
        *,
        ordinal: int | None = None,
        query_release_ns: int | None = None,
        response_delay_ns: int | None = None,
    ) -> int:
        with self.query_lock:
            if self.process is None or self.codec is None or self.process.stdin is None:
                raise RuntimeError("online SimplePIR is not active")
            request: dict[str, Any] = {"operation_id": operation_id, "index": index}
            if ordinal is not None:
                request.update(
                    {
                        "ordinal": ordinal,
                        "query_release_ns": int(query_release_ns or 0),
                        "response_delay_ns": int(response_delay_ns or 0),
                        "public_period_ns": self.cover_period_ms * 1_000_000,
                    }
                )
            self.process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
            return time.monotonic_ns()

    def _execute_query(self, operation_id: str, index: int) -> AgentDescriptorV7:
        send_ns = self._submit_query(operation_id, index)
        return self._await_response(operation_id, index, send_ns)

    def has_cached_descriptor(self, index: int) -> bool:
        return (EPOCH, index) in self.descriptor_cache

    def resolve_descriptor(
        self, operation_id: str, index: int, *, allow_cache_miss: bool = True
    ) -> AgentDescriptorV7:
        """Resolve once per authenticated descriptor epoch, never per Tool action."""

        with self.descriptor_cache_lock:
            key = (EPOCH, index)
            cached = self.descriptor_cache.get(key)
            if cached is not None:
                self.descriptor_cache_hits += 1
                self.descriptor_cache_events.append(
                    {
                        "operation_id": operation_id,
                        "agent_id": index,
                        "catalog_epoch": EPOCH,
                        "cache_hit": True,
                    }
                )
                return cached
            if not allow_cache_miss:
                raise OnlineSessionFailure("PIR_REAL_RESOLUTION_ADMISSION_CLOSED")
            self.descriptor_cache_misses += 1
            value = self.query(operation_id, index)
            self.descriptor_cache[key] = value
            self.descriptor_cache_events.append(
                {
                    "operation_id": operation_id,
                    "agent_id": index,
                    "catalog_epoch": EPOCH,
                    "cache_hit": False,
                }
            )
            return value

    def start_cover_schedule(
        self,
        *,
        opportunities: int,
        period_ms: int,
        dummy_index: int = 999,
        initial_lead_ms: int = 25,
        epoch_ms: int = 6000,
        query_completion_bound_ms: int = 50,
        liveness_cap_ms: int = 60_000,
        commitment_lead_ms: int = 0,
        answer_release_delay_ms: int = 0,
        worker_lanes: int = 0,
        max_inflight: int = 0,
    ) -> None:
        if self.cover_thread is not None:
            raise RuntimeError("PIR cover schedule already started")
        if epoch_ms not in (6000, 8000, 10000):
            raise ValueError(
                "PIR public epoch is outside the predeclared development candidates"
            )
        if period_ms not in (60, 75, 100):
            raise ValueError("PIR period is outside the predeclared candidates")
        if epoch_ms % period_ms or opportunities != epoch_ms // period_ms:
            raise ValueError(
                "fixed PIR opportunities must be derived from public epoch / period"
            )
        if dummy_index != 999 or dummy_index >= self.record_count:
            raise ValueError("invalid frozen dummy PIR descriptor row")
        if initial_lead_ms != 25:
            raise ValueError(
                "V12 timing profile requires the frozen 25 ms PIR initial lead"
            )
        if query_completion_bound_ms != 50:
            raise ValueError("V12 timing PIR query completion bound changed")
        if liveness_cap_ms != 60_000:
            raise ValueError("PIR cover liveness cap changed")
        duplex = any(
            (commitment_lead_ms, answer_release_delay_ms, worker_lanes, max_inflight)
        )
        if duplex and (
            commitment_lead_ms not in (5, 20)
            or answer_release_delay_ms != 50
            or worker_lanes != 1
            or max_inflight != opportunities
        ):
            raise ValueError("V12 duplex Registry clock parameters changed")
        self.cover_opportunities = opportunities
        self.cover_period_ms = period_ms
        self.cover_dummy_index = dummy_index
        self.cover_initial_lead_ms = initial_lead_ms
        self.query_completion_bound_ms = query_completion_bound_ms
        self.cover_liveness_cap_ms = liveness_cap_ms
        self.pir_commitment_lead_ms = commitment_lead_ms
        self.registry_answer_release_delay_ms = answer_release_delay_ms
        self.registry_worker_lanes = worker_lanes
        self.registry_max_inflight = max_inflight
        self.cover_origin_ns = time.monotonic_ns()
        target = self._run_duplex_cover_schedule if duplex else self._run_cover_schedule
        self.cover_thread = threading.Thread(target=target, daemon=True)
        self.cover_thread.start()

    def _run_completion_loop(self) -> None:
        assert self.completion_queue is not None
        while True:
            submitted = self.completion_queue.get()
            try:
                if submitted is None:
                    return
                try:
                    result = self._await_response(
                        submitted.operation_id,
                        submitted.index,
                        submitted.send_monotonic_ns,
                        # Public query/answer release is already bounded by its
                        # own open-loop clocks. The private consumer must not
                        # reinterpret ordinary host scheduling jitter as a
                        # missing public response or perturb the sender.
                        timeout_ms=self.cover_liveness_cap_ms,
                    )
                    if submitted.pending is not None:
                        submitted.pending.result = result
                        self.real_query_count += 1
                    else:
                        self.dummy_query_count += 1
                except _PIRPreparationDeferred:
                    submitted.event["private_preparation_deferred"] = True
                    self.dummy_query_count += 1
                    if submitted.pending is not None:
                        with self.cover_condition:
                            if self.cover_complete:
                                submitted.pending.error = RuntimeError(
                                    "PIR cover opportunities exhausted"
                                )
                                submitted.pending.ready.set()
                            else:
                                self.cover_pending.appendleft(submitted.pending)
                                self.cover_condition.notify_all()
                except BaseException as exc:
                    if self.cover_error is None:
                        self.cover_error = exc
                    if submitted.pending is not None:
                        submitted.pending.error = exc
                finally:
                    submitted.event["complete_ns"] = (
                        time.monotonic_ns() - self.cover_origin_ns
                    )
                    if (
                        submitted.pending is not None
                        and not submitted.event.get("private_preparation_deferred")
                    ):
                        submitted.pending.ready.set()
            finally:
                self.completion_queue.task_done()

    def _run_duplex_cover_schedule(self) -> None:
        start_ns = self.cover_origin_ns or time.monotonic_ns()
        period_ns = self.cover_period_ms * 1_000_000
        lead_ns = self.pir_commitment_lead_ms * 1_000_000
        previous_send_ns = 0
        self.completion_queue = queue.Queue(maxsize=self.registry_max_inflight)
        self.completion_thread = threading.Thread(
            target=self._run_completion_loop, daemon=True
        )
        self.completion_thread.start()
        try:
            for ordinal in range(self.cover_opportunities):
                nominal_ns, eligible_ns, cutoff_ns = duplex_pir_opportunity_times(
                    origin_ns=start_ns,
                    ordinal=ordinal,
                    period_ns=period_ns,
                    initial_lead_ns=self.cover_initial_lead_ms * 1_000_000,
                    commitment_lead_ns=lead_ns,
                    previous_public_send_ns=previous_send_ns,
                )
                remaining_ns = cutoff_ns - time.monotonic_ns()
                if remaining_ns > 0:
                    time.sleep(remaining_ns / 1_000_000_000)
                with self.cover_condition:
                    pending = None
                    if (
                        self.cover_pending
                        and self.cover_pending[0].enqueued_ns <= cutoff_ns
                    ):
                        pending = self.cover_pending.popleft()
                committed_ns = time.monotonic_ns()
                real = pending is not None
                operation_id = (
                    pending.operation_id if pending else f"pir-cover-{ordinal + 1:06d}"
                )
                index = pending.index if pending else self.cover_dummy_index
                event: dict[str, Any] = {
                    "ordinal": ordinal,
                    "nominal_ns": nominal_ns - start_ns,
                    "eligible_ns": eligible_ns - start_ns,
                    "commitment_cutoff_ns": cutoff_ns - start_ns,
                    "committed_ns": committed_ns - start_ns,
                    "real": real,
                    "expired_opportunity_retrofilled": False,
                }
                self.cover_events.append(event)
                now_monotonic_ns = time.monotonic_ns()
                query_release_wall_ns = time.time_ns() + max(
                    0, eligible_ns - now_monotonic_ns
                )
                try:
                    send_ns = self._submit_query(
                        operation_id,
                        index,
                        ordinal=ordinal,
                        query_release_ns=query_release_wall_ns,
                        response_delay_ns=(
                            self.registry_answer_release_delay_ms * 1_000_000
                        ),
                    )
                    event["private_preparation_enqueue_ns"] = send_ns - start_ns
                    event["query_release_ns"] = query_release_wall_ns
                    event["response_delay_ns"] = (
                        self.registry_answer_release_delay_ms * 1_000_000
                    )
                    assert self.completion_queue is not None
                    self.completion_queue.put(
                        _SubmittedPIRQuery(
                            operation_id,
                            index,
                            pending,
                            event,
                            send_ns,
                        )
                    )
                except BaseException as exc:
                    if self.cover_error is None:
                        self.cover_error = exc
                    event["complete_ns"] = time.monotonic_ns() - start_ns
                    if pending is not None:
                        pending.error = exc
                        pending.ready.set()
            assert self.completion_queue is not None
            self.completion_queue.join()
            self.completion_queue.put(None)
            self.completion_queue.join()
            if self.completion_thread is not None:
                self.completion_thread.join(timeout=2)
        except BaseException as exc:
            if self.cover_error is None:
                self.cover_error = exc
        finally:
            with self.cover_condition:
                self.cover_complete = True
                while self.cover_pending:
                    pending = self.cover_pending.popleft()
                    pending.error = self.cover_error or RuntimeError(
                        "PIR cover opportunities exhausted"
                    )
                    pending.ready.set()
                self.cover_condition.notify_all()

    def _run_cover_schedule(self) -> None:
        start_ns = self.cover_origin_ns or time.monotonic_ns()
        period_ns = self.cover_period_ms * 1_000_000
        previous_send_ns = 0
        try:
            for ordinal in range(self.cover_opportunities):
                nominal_ns = (
                    start_ns
                    + self.cover_initial_lead_ms * 1_000_000
                    + ordinal * period_ns
                )
                eligible_ns = nominal_ns
                if ordinal and previous_send_ns + period_ns > eligible_ns:
                    eligible_ns = previous_send_ns + period_ns
                remaining_ns = eligible_ns - time.monotonic_ns()
                if remaining_ns > 0:
                    time.sleep(remaining_ns / 1_000_000_000)
                send_ns = time.monotonic_ns()
                if send_ns - start_ns > self.cover_liveness_cap_ms * 1_000_000:
                    raise TimeoutError(
                        "PIR cover schedule exceeded public liveness cap"
                    )
                with self.cover_condition:
                    pending = (
                        self.cover_pending.popleft() if self.cover_pending else None
                    )
                real = pending is not None
                operation_id = (
                    pending.operation_id if pending else f"pir-cover-{ordinal + 1:06d}"
                )
                index = pending.index if pending else self.cover_dummy_index
                try:
                    result = self._execute_query(operation_id, index)
                    if pending is not None:
                        pending.result = result
                except BaseException as exc:
                    if pending is not None:
                        pending.error = exc
                    raise
                finally:
                    complete_ns = time.monotonic_ns()
                    self.cover_events.append(
                        {
                            "ordinal": ordinal,
                            "nominal_ns": nominal_ns - start_ns,
                            "eligible_ns": eligible_ns - start_ns,
                            "send_ns": send_ns - start_ns,
                            "complete_ns": complete_ns - start_ns,
                            "real": real,
                        }
                    )
                    if pending is not None:
                        pending.ready.set()
                if real:
                    self.real_query_count += 1
                else:
                    self.dummy_query_count += 1
                previous_send_ns = send_ns
        except BaseException as exc:
            self.cover_error = exc
        finally:
            with self.cover_condition:
                self.cover_complete = True
                while self.cover_pending:
                    pending = self.cover_pending.popleft()
                    pending.error = self.cover_error or RuntimeError(
                        "PIR cover opportunities exhausted"
                    )
                    pending.ready.set()
                self.cover_condition.notify_all()

    def query(self, operation_id: str, index: int) -> AgentDescriptorV7:
        if self.cover_thread is None:
            return self._execute_query(operation_id, index)
        pending = _PendingPIRResolution(operation_id, index, time.monotonic_ns())
        with self.cover_condition:
            if self.cover_complete:
                raise RuntimeError("PIR cover opportunities exhausted")
            self.cover_pending.append(pending)
            self.cover_condition.notify_all()
        if not pending.ready.wait(self.cover_liveness_cap_ms / 1000):
            raise TimeoutError("PIR resolution exceeded public liveness cap")
        if pending.error is not None:
            raise pending.error
        if pending.result is None:
            raise RuntimeError("PIR cover opportunity did not return a descriptor")
        return pending.result

    def __exit__(self, *_args: object) -> None:
        if self.process is None:
            return
        cover_failure: BaseException | None = None
        try:
            if self.cover_thread is not None:
                self.cover_thread.join(timeout=self.cover_liveness_cap_ms / 1000 + 5)
                if self.cover_thread.is_alive():
                    cover_failure = TimeoutError(
                        "PIR cover scheduler did not terminate"
                    )
                elif self.cover_error is not None:
                    cover_failure = self.cover_error
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
            if self.stdout_thread is not None:
                self.stdout_thread.join(timeout=2)
            (self.output / "bridge_stderr.txt").write_text(
                "".join(self.stderr_lines), encoding="utf-8"
            )
            (self.output / "online_query_summary.json").write_text(
                json.dumps(
                    {
                        "official_simplepir": True,
                        "commit": SIMPLEPIR_COMMIT,
                        "query_count": self.query_count,
                        "real_query_count": self.real_query_count,
                        "dummy_query_count": self.dummy_query_count,
                        "fixed_cover_opportunities": self.cover_opportunities,
                        "cover_period_ms": self.cover_period_ms,
                        "cover_initial_lead_ms": self.cover_initial_lead_ms,
                        "query_completion_bound_ms": self.query_completion_bound_ms,
                        "pir_commitment_lead_ms": self.pir_commitment_lead_ms,
                        "registry_answer_release_delay_ms": self.registry_answer_release_delay_ms,
                        "registry_worker_lanes": self.registry_worker_lanes,
                        "registry_max_inflight": self.registry_max_inflight,
                        "query_sender_waits_for_prior_completion": False
                        if self.pir_commitment_lead_ms
                        else True,
                        "descriptor_cache_hits": self.descriptor_cache_hits,
                        "descriptor_cache_misses": self.descriptor_cache_misses,
                        "cached_descriptor_count": len(self.descriptor_cache),
                        "fresh_query_hashes": len(self.query_hashes)
                        == len(set(self.query_hashes)),
                        "future_indices_in_startup": 0,
                        "prebuilt_bridge_binary": self.prebuilt_bridge_used,
                        "record_count": self.record_count,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            if self.cover_thread is not None:
                (self.output / "private_pir_cover_schedule.json").write_text(
                    json.dumps(self.cover_events, indent=2) + "\n", encoding="utf-8"
                )
                (self.output / "private_descriptor_cache_events.json").write_text(
                    json.dumps(self.descriptor_cache_events, indent=2) + "\n",
                    encoding="utf-8",
                )
            if cover_failure is not None:
                raise cover_failure
        finally:
            # Popen does not close PIPE file objects merely because the child
            # exited.  Release every descriptor even when shutdown or evidence
            # serialization fails.
            for stream in (
                self.process.stdin,
                self.process.stdout,
                self.process.stderr,
            ):
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
        timing_profile = (
            getattr(public_profile, "profile_class", "")
            == "TIMING_INDISTINGUISHABILITY_PROFILE"
        )
        timing_revision = getattr(public_profile, "timing_semantic_revision", "")
        if runner_binary is not None:
            self.runner_binary = runner_binary
        elif timing_revision in {
            "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4",
            "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R1",
            "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R2",
            "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R3",
            "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R4",
            "DUPLEX_PUBLIC_TIMING_VIRTUALIZATION_V4R5",
        }:
            self.runner_binary = DUPLEX_TIMING_RUNNER
        elif timing_revision == "EFFECTIVE_PUBLIC_CLOCK_V3":
            self.runner_binary = DELTA_FUNCTIONAL_RUNNER
        elif timing_revision == "EFFECTIVE_PUBLIC_CLOCK_V2":
            self.runner_binary = CAUSAL_HORIZON_RUNNER
        elif timing_profile:
            self.runner_binary = TIMING_RUNNER
        else:
            self.runner_binary = DEFAULT_RUNNER
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

    def __enter__(self) -> CanonicalOnlineSession:
        if self.output.exists():
            raise FileExistsError(
                f"refusing to overwrite online evidence: {self.output}"
            )
        self.output.mkdir(parents=True)
        if not self.runner_binary.is_file():
            raise FileNotFoundError(
                f"V11.2 online runner is missing: {self.runner_binary}"
            )
        self.providers = V11EvidenceProviders(
            self.cases, self.output / "private_provider_evidence.json"
        )
        self.pir = OnlineSimplePIRResolver(
            self.output / "pir",
            record_count=self.pir_record_count,
            bridge_binary=(
                TIMING_PIR_BRIDGE
                if getattr(self.public_profile, "profile_class", "")
                == "TIMING_INDISTINGUISHABILITY_PROFILE"
                else None
            ),
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
                raise ValueError(
                    f"unsupported online development override: {sorted(unknown)}"
                )
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
            self._wait(
                lambda: any(
                    event.get("type") == "SESSION_READY" for event in self.events
                ),
                timeout=10,
            )
            if (
                getattr(profile, "profile_class", "")
                == "TIMING_INDISTINGUISHABILITY_PROFILE"
            ):
                self.pir.start_cover_schedule(
                    opportunities=int(profile.pir_resolution_opportunities),
                    period_ms=int(profile.pir_resolution_period_ms),
                    dummy_index=int(profile.dummy_descriptor_row),
                    initial_lead_ms=int(profile.pir_initial_lead_ms),
                    epoch_ms=int(profile.pir_public_epoch_ms),
                    query_completion_bound_ms=int(
                        profile.pir_query_completion_bound_ms
                    ),
                    liveness_cap_ms=int(profile.public_session_liveness_cap_ms),
                    commitment_lead_ms=int(
                        getattr(profile, "pir_commitment_lead_ms", 0)
                    ),
                    answer_release_delay_ms=int(
                        getattr(profile, "registry_answer_release_delay_ms", 0)
                    ),
                    worker_lanes=int(getattr(profile, "registry_worker_lanes", 0)),
                    max_inflight=int(getattr(profile, "registry_max_inflight", 0)),
                )
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
                    self.failures[str(event.get("operation_id", ""))] = str(
                        event.get("reason", "ACTION_REJECTED")
                    )
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

    def submit(
        self, case: V11ActionCase, arguments: dict[str, Any]
    ) -> V11ActionOutcome:
        case.validate()
        if arguments != case.argument_schema.validate_values(case.arguments):
            raise AssertionError("framework changed online structured arguments")
        if case.operation_id not in self.cases:
            raise ValueError(
                "case was not registered with the online development session"
            )
        if self.decision_delay_ms and any(
            item["stage"] == "FRAMEWORK_RESULT_DELIVERED" for item in self.lifecycle
        ):
            time.sleep(self.decision_delay_ms / 1000)
        self._record("ACTION_INTENT_SUBMITTED", case.operation_id)
        assert self.pir is not None
        agent_id, agent_capability, capability, kind = _canonical_ids(case)
        if self.pir_delay_ms:
            time.sleep(self.pir_delay_ms / 1000)
        allow_cache_miss = True
        if (
            getattr(self.public_profile, "profile_class", "")
            == "TIMING_INDISTINGUISHABILITY_PROFILE"
        ):
            elapsed_ms = (time.monotonic_ns() - self.pir.cover_origin_ns) / 1_000_000
            cutoff_ms = int(self.public_profile.pir_real_resolution_arrival_cutoff_ms)
            allow_cache_miss = elapsed_ms < cutoff_ms
        selected = self.pir.resolve_descriptor(
            case.operation_id, agent_id, allow_cache_miss=allow_cache_miss
        )
        self._record(
            "DYNAMIC_PIR_DESCRIPTOR_RECOVERED", case.operation_id, agent_id=agent_id
        )
        protected = ProtectedActionIntent(
            capability,
            protected_payload(case),
            "v11-2-online-development",
            case.operation_id,
            kind,
        )
        if case.placement == "TRUSTED_MODULE_LOCAL":
            resolved = TrustedActionRouter({}).resolve(
                protected, selected, PrivacyProfile.STRICT
            )
            if resolved.placement.value != "TRUSTED_MODULE_LOCAL":
                raise AssertionError(
                    "dynamic internal Agent resolved outside trusted module"
                )
            self._record(
                "ACTION_ADMITTED", case.operation_id, placement="TRUSTED_MODULE_LOCAL"
            )
            outcome = LocalTrustedBackendV11().execute_internal(case)
            assert self._ledger is not None
            with self._delivery_lock:
                self._ledger.record_received(case.operation_id)
                self._ledger.mark_decapsulated(case.operation_id)
                sink: list[str] = []
                self._ledger.deliver(
                    case.operation_id, lambda: sink.append(outcome.result)
                )
            self._record(
                "FRAMEWORK_RESULT_DELIVERED",
                case.operation_id,
                placement="TRUSTED_MODULE_LOCAL",
            )
            return outcome

        session = CanonicalSessionSpec(
            case.case_id, agent_capability, agent_id, (protected,)
        )
        resolved_actions = resolve_session(session, selected)
        action = resolved_actions[0]
        if action["effect_semantics"] != case.effect_semantics:
            raise AssertionError("dynamic trusted route changed effect semantics")
        assert self.process is not None and self.process.stdin is not None
        try:
            self.process.stdin.write(
                json.dumps({"type": "SUBMIT_RESOLVED_ACTION", "action": action}) + "\n"
            )
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise OnlineSessionFailure("PROFILE_ADMISSION_CLOSED") from exc
        self._wait(
            lambda: (
                case.operation_id in self.results or case.operation_id in self.failures
            ),
            timeout=10,
        )
        if case.operation_id in self.failures:
            raise OnlineSessionFailure(self.failures[case.operation_id])
        event = self.results[case.operation_id]
        item = event["result"]
        status = int(item["status"])
        payload = base64.b64decode(item.get("payload") or "").decode(
            "utf-8", errors="replace"
        )
        if case.scenario == "SUCCESS" and status == 2:
            semantics = f"{case.effect_semantics}:SUCCESS"
            result = payload
        elif (
            case.scenario in {"BOUNDED_TIMEOUT", "AMBIGUOUS_RESTART"}
            and case.effect_semantics == "NON_IDEMPOTENT_EFFECT"
        ):
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
        self._record(
            "FRAMEWORK_RESULT_DELIVERED",
            case.operation_id,
            result_round=int(event.get("round", 0)),
        )
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
        close_timeout = 15
        if (
            getattr(self.public_profile, "profile_class", "")
            == "TIMING_INDISTINGUISHABILITY_PROFILE"
        ):
            close_timeout = (
                int(self.public_profile.public_session_liveness_cap_ms / 1000) + 5
            )
        try:
            return_code = self.process.wait(timeout=close_timeout)
        except subprocess.TimeoutExpired as exc:
            self.process.kill()
            self.process.wait(timeout=5)
            raise OnlineSessionFailure(
                "online runner did not stop at public session end"
            ) from exc
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
        self.trace = json.loads(
            (self.output / "go_online_result.json").read_text(encoding="utf-8")
        )
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
                for stream in (
                    self.process.stdin,
                    self.process.stdout,
                    self.process.stderr,
                ):
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
        return strict_structural_projection(
            self.trace, profile
        ), strict_size_projection(self.trace, profile)

    def causal_proof(self) -> dict[str, Any]:
        submitted = {
            item["operation_id"]: item["monotonic_ns"]
            for item in self.lifecycle
            if item["stage"] == "ACTION_INTENT_SUBMITTED"
        }
        delivered = {
            item["operation_id"]: item["monotonic_ns"]
            for item in self.lifecycle
            if item["stage"] == "FRAMEWORK_RESULT_DELIVERED"
        }
        ids = [case.operation_id for case in self.cases.values()]
        checks = []
        for parent, child in zip(ids, ids[1:]):
            checks.append(
                {
                    "parent": parent,
                    "child": child,
                    "child_submitted_after_parent_delivery": submitted.get(child, 0)
                    > delivered.get(parent, 2**63),
                }
            )
        return {
            "startup_action_count": 0,
            "pre_t0_action_queue_count": 0,
            "checks": checks,
            "passed": all(
                item["child_submitted_after_parent_delivery"] for item in checks
            ),
        }

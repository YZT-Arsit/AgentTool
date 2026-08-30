from __future__ import annotations

import io
import hashlib
import json
import os
from pathlib import Path

import pytest

import v11_online.session as online
from scripts.run_v11_3_profile_closure import strict_cases
from v11a_confirmatory.orchestrator import ExecutionPermit
from scripts import run_v12_confirmatory as v12_driver
from scripts.run_v12_performance import canonical_boundary_latency_ms
from scripts.reanalyze_v12_profile_requalification import functional as requalification_functional


class _FakePopen:
    def __init__(self, command: list[str]):
        self.command = command
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(
            json.dumps({"future_indices_received": 0, "records": 1000, "type": "PIR_READY"})
            + "\n"
        )
        self.stderr = io.StringIO()
        self.returncode = None

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        self.returncode = 0
        return 0

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9

    def poll(self) -> int | None:
        return self.returncode


def test_verified_prebuilt_simplepir_does_not_require_go_or_gcc(monkeypatch, tmp_path: Path) -> None:
    bridge = tmp_path / "pir_integration" / "simplepir_bridge"
    bridge.mkdir(parents=True)
    binary = bridge / ("acv-simplepir-online.exe" if os.name == "nt" else "acv-simplepir-online")
    binary.write_bytes(b"frozen-dev-binary")
    launched: list[_FakePopen] = []

    def fake_popen(command, **_kwargs):
        value = _FakePopen(list(command))
        launched.append(value)
        return value

    monkeypatch.setattr(online, "ROOT", tmp_path)
    monkeypatch.setattr(online.subprocess, "Popen", fake_popen)
    resolver = online.OnlineSimplePIRResolver(tmp_path / "evidence")
    with resolver:
        assert resolver.prebuilt_bridge_used
        assert launched[0].command[0] == str(binary)
        assert "go" not in launched[0].command

    assert launched[0].stdin.closed
    assert launched[0].stdout.closed
    assert launched[0].stderr.closed


def test_partial_online_session_entry_releases_started_providers(monkeypatch, tmp_path: Path) -> None:
    runner = tmp_path / "runner"
    runner.write_bytes(b"runner")
    events: list[str] = []

    class Providers:
        def __init__(self, _cases):
            self.endpoints = {}

        def __enter__(self):
            events.append("providers_enter")
            return self

        def __exit__(self, *_args):
            events.append("providers_exit")

    class PIR:
        def __init__(self, _output, **_kwargs):
            self.query_count = 0
            self.query_hashes = []

        def __enter__(self):
            events.append("pir_enter")
            raise FileNotFoundError("development startup failure")

        def __exit__(self, *_args):
            events.append("pir_exit")

    monkeypatch.setattr(online, "V11EvidenceProviders", Providers)
    monkeypatch.setattr(online, "OnlineSimplePIRResolver", PIR)
    session = online.CanonicalOnlineSession(tmp_path / "run", [], runner_binary=runner)
    with pytest.raises(FileNotFoundError, match="development startup failure"):
        session.__enter__()

    assert events == ["providers_enter", "pir_enter", "pir_exit", "providers_exit"]
    assert session.providers is None
    assert session.pir is None


def test_v12_execution_permit_requires_capability_preflight() -> None:
    case = strict_cases(1, "DEV-V12-PERMIT")[0]
    with pytest.raises(PermissionError, match="capability preflight"):
        ExecutionPermit("V12", True).require([case])
    ExecutionPermit("V12", True, capability_preflight_passed=True).require([case])


def test_public_profile_config_epoch_mutation_fails_artifact_binding(tmp_path: Path) -> None:
    profile = tmp_path / "PUBLIC_PROFILE_ONLINE_V11_4.json"
    frozen = b'{"config_epoch":3}\n'
    profile.write_bytes(frozen)
    manifest = {
        "files": [
            {
                "path": profile.name,
                "sha256": hashlib.sha256(frozen).hexdigest(),
            }
        ]
    }
    assert v12_driver.verify_frozen_files(manifest, root=tmp_path)
    profile.write_bytes(b'{"config_epoch":4}\n')
    assert not v12_driver.verify_frozen_files(manifest, root=tmp_path)


def test_performance_boundary_latency_uses_actual_private_trajectory(tmp_path: Path) -> None:
    lifecycle = [
        {"stage": "ACTION_INTENT_SUBMITTED", "operation_id": "op-a", "monotonic_ns": 1_000_000},
        {"stage": "FRAMEWORK_RESULT_DELIVERED", "operation_id": "op-a", "monotonic_ns": 4_000_000},
        {"stage": "ACTION_INTENT_SUBMITTED", "operation_id": "op-b", "monotonic_ns": 10_000_000},
        {"stage": "FRAMEWORK_RESULT_DELIVERED", "operation_id": "op-b", "monotonic_ns": 15_000_000},
    ]
    (tmp_path / "private_trajectory.json").write_text(json.dumps(lifecycle), encoding="utf-8")
    assert canonical_boundary_latency_ms(tmp_path) == 4.0


def test_profile_reanalysis_requires_causal_proof_only_for_dynamic_sequence() -> None:
    common = {
        "trace_gate": {"passed": True},
        "semantic_equal": True,
        "dynamic_pir": True,
        "error": "",
        "causal_proof": {"passed": False},
    }
    assert requalification_functional({**common, "workflow": "PARALLEL_ACTIONS"})
    assert not requalification_functional({**common, "workflow": "DYNAMIC_SEQUENCE"})
    assert requalification_functional(
        {
            **common,
            "workflow": "DYNAMIC_SEQUENCE",
            "causal_proof": {"passed": True},
        }
    )

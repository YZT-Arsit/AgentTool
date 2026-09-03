from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_EVIDENCE = "7a188ae2ebfcc42313eca0dbf92c62dfc66ff3fb"
RUNTIME_SOURCE = "63319014f560f46e2a46dd140f53551e43c27e0d"
BRANCH = "v12-duplex-timing-virtualization-redesign"
FRAMEWORKS = ("OpenAI Agents SDK", "Microsoft Agent Framework")
WORKLOADS = (
    "ORDINARY_TOOL",
    "AGENT_AS_TOOL_TRANSITION",
    "CACHE_REUSE_30",
    "CAPACITY_50",
)
CONFIGURATIONS = ("NATIVE", "OAE_V4R8")
WARMUPS = 2
MEASURED_REPETITIONS = 30
FREEZE_PATH = ROOT / "V12_V4R8_FINAL_UTILITY_FREEZE.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def framework_code(framework: str) -> str:
    return "OA" if framework == "OpenAI Agents SDK" else "MS"


def identity(
    framework: str,
    workload: str,
    configuration: str,
    kind: str,
    repetition: int,
) -> str:
    return (
        "DEV-V4R8-FINAL-UTILITY-"
        f"{framework_code(framework)}-{workload}-{configuration}-{kind}{repetition:03d}"
    )


def schedule() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    ordinal = 0
    # Warmups are frozen, recorded, and deliberately excluded from measurement.
    for framework in FRAMEWORKS:
        for workload in WORKLOADS:
            for warmup in range(1, WARMUPS + 1):
                for configuration in (
                    CONFIGURATIONS if warmup % 2 else tuple(reversed(CONFIGURATIONS))
                ):
                    ordinal += 1
                    rows.append(
                        {
                            "ordinal": ordinal,
                            "kind": "WARMUP",
                            "framework": framework,
                            "workload": workload,
                            "configuration": configuration,
                            "repetition": warmup,
                            "pair_order": "NATIVE_THEN_OAE"
                            if warmup % 2
                            else "OAE_THEN_NATIVE",
                            "identity": identity(
                                framework,
                                workload,
                                configuration,
                                "W",
                                warmup,
                            ),
                        }
                    )
    # Round-robin coordinates across repetitions to reduce long-run host drift.
    for repetition in range(1, MEASURED_REPETITIONS + 1):
        order = CONFIGURATIONS if repetition % 2 else tuple(reversed(CONFIGURATIONS))
        for framework in FRAMEWORKS:
            for workload in WORKLOADS:
                for configuration in order:
                    ordinal += 1
                    rows.append(
                        {
                            "ordinal": ordinal,
                            "kind": "MEASURED",
                            "framework": framework,
                            "workload": workload,
                            "configuration": configuration,
                            "repetition": repetition,
                            "pair_order": "NATIVE_THEN_OAE"
                            if repetition % 2
                            else "OAE_THEN_NATIVE",
                            "identity": identity(
                                framework,
                                workload,
                                configuration,
                                "M",
                                repetition,
                            ),
                        }
                    )
    return rows


def main() -> int:
    if FREEZE_PATH.exists():
        raise FileExistsError(f"refusing to overwrite freeze: {FREEZE_PATH}")
    if git("rev-parse", "HEAD") != BASE_EVIDENCE:
        raise RuntimeError("utility freeze must be created from the V4R8 closure HEAD")
    changed = git("diff", "--name-only", f"{RUNTIME_SOURCE}..HEAD").splitlines()
    protected_prefixes = (
        "common_action_gateway_v2/",
        "pir_integration/",
        "v11_online/",
        "v11_full_scope/",
        "v12_timing/",
    )
    protected_diff = [path for path in changed if path.startswith(protected_prefixes)]
    if protected_diff:
        raise RuntimeError(f"protected runtime differs from V4R8: {protected_diff}")
    rows = schedule()
    identities = [str(row["identity"]) for row in rows]
    measured = [row for row in rows if row["kind"] == "MEASURED"]
    warmups = [row for row in rows if row["kind"] == "WARMUP"]
    if len(rows) != 512 or len(measured) != 480 or len(warmups) != 32:
        raise AssertionError("utility schedule denominator is malformed")
    if len(set(identities)) != len(identities):
        raise AssertionError("utility identities are not unique")
    prior_identity_sources = tuple(ROOT.glob("V12*FREEZE*.json"))
    for source in prior_identity_sources:
        payload = source.read_text(encoding="utf-8", errors="replace")
        overlap = next((value for value in identities if value in payload), None)
        if overlap:
            raise AssertionError(
                f"fresh utility identity reused in {source}: {overlap}"
            )

    profile = json.loads(
        (ROOT / "V12_V4R8_RESPONSE_ANCHOR_SMOKE_FREEZE.json").read_text(
            encoding="utf-8"
        )
    )["profile"]
    evidence_inventory = {
        "adequate_final_v4r8_utility_measurement": False,
        "reason": (
            "No final-V4R8 artifact contains at least 30 NATIVE and 30 OAE_V4R8 "
            "measurements for every one of the eight required framework/workload coordinates."
        ),
        "existing_v4r8_smoke": {
            "path": "V12_V4R8_RESPONSE_ANCHOR_REPAIR_EVIDENCE/CLOSURE.json",
            "sessions": 640,
            "role": "timing-repair development smoke, not utility benchmark",
        },
        "existing_v4r8_functional": {
            "path": "V12_V4R7_BOUNDED_LIVENESS_CLOSURE_EVIDENCE/BOUNDED_LIVENESS_FUNCTIONAL_SUMMARY.json",
            "role": "single-run functional qualification inherited unchanged by V4R8",
            "minimum_repetitions_per_required_configuration": 1,
        },
        "historical_v4r6_v4r7_latency_reused": False,
    }
    value = {
        "schema": "AgentTool.V12V4R8FinalUtilityFreeze/1",
        "phase": "V12-V4R8-FINAL-UTILITY-OVERHEAD-AND-SERVER-TERMINATION-CLOSURE",
        "base_v4r8_evidence": BASE_EVIDENCE,
        "runtime_source_commit": RUNTIME_SOURCE,
        "branch": BRANCH,
        "frozen_before_execution": True,
        "privacy_experiment": False,
        "classifier_runs": 0,
        "auc_calculations": 0,
        "retries": 0,
        "replacements": 0,
        "existing_final_v4r8_utility_evidence": evidence_inventory,
        "profile": profile,
        "frameworks": list(FRAMEWORKS),
        "workloads": list(WORKLOADS),
        "configurations": list(CONFIGURATIONS),
        "warmups_per_coordinate_configuration": WARMUPS,
        "measured_repetitions_per_coordinate_configuration": MEASURED_REPETITIONS,
        "planned_warmups": len(warmups),
        "planned_measured_executions": len(measured),
        "execution_order": (
            "round-robin framework/workload coordinates; odd repetitions NATIVE then "
            "OAE_V4R8; even repetitions OAE_V4R8 then NATIVE"
        ),
        "latency_boundaries": {
            "semantic_completion_ms": (
                "immediately before pinned framework workflow invocation through return "
                "of the final expected framework-visible semantic result"
            ),
            "public_session_wall_ms": (
                "CanonicalOnlineSession SESSION_T0 monotonic record through completion "
                "of the fixed Relay and Registry obligations and session resource close"
            ),
        },
        "schedule": rows,
        "protected_runtime_diff_from_runtime_source": protected_diff,
        "source_hashes_before_freeze": {
            "v4r8_profile": sha256(ROOT / "v12_timing" / "profile.py"),
            "online_session": sha256(ROOT / "v11_online" / "session.py"),
            "frameworks": sha256(ROOT / "v11_online" / "frameworks.py"),
            "workload_builder": sha256(
                ROOT / "scripts" / "run_v12_duplex_functional.py"
            ),
            "bounded_capacity_runner": sha256(
                ROOT / "scripts" / "run_v12_v4r7_bounded_liveness_functional.py"
            ),
            "benchmark_runner": sha256(
                ROOT / "scripts" / "run_v12_v4r8_final_utility.py"
            ),
        },
    }
    FREEZE_PATH.write_text(
        json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"freeze": str(FREEZE_PATH), "planned": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

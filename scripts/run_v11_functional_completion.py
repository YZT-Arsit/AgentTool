from __future__ import annotations

import csv
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v11_full_scope.canonical import (
    canonical_external_outcome,
    canonical_internal_outcome,
    canonical_multi_action,
    public_projections,
)
from v11_full_scope.fixtures import agent_case, tool_case, with_readiness
from v11_full_scope.models import AgentServiceSubtype, CanonicalActionFamily
from v11_full_scope.structural import run_development_pair


OUTPUT = ROOT / "results_v11_development" / "functional_completion_run2"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing overwrite: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    rows: list[dict[str, object]] = []

    for count in (1, 10, 50):
        cases = [
            replace(
                tool_case(f"completion-multi-{count}-{index}", "FRAMEWORK_NEUTRAL"),
                operation_id=f"v11run2{count:02d}{index:03d}",
            )
            for index in range(count)
        ]
        try:
            value = canonical_multi_action(cases, OUTPUT / "raw" / f"multi-{count}")
            rows.append({
                "gate": f"TOOL_{count}",
                "functional": value["functional"],
                "admitted": value["admitted"],
                "delivered": value["delivered"],
                "dummy_provider_operations": value["dummy_provider_operations"],
                "profile_overflow_events": value["profile_overflow_events"],
                "error": "",
            })
        except Exception as error:  # development evidence must preserve infrastructure failures
            rows.append({
                "gate": f"TOOL_{count}", "functional": False, "admitted": count,
                "delivered": "", "dummy_provider_operations": "", "profile_overflow_events": "",
                "error": f"{type(error).__name__}: {error}",
            })

    external = replace(
        tool_case("completion-external", "FRAMEWORK_NEUTRAL"),
        action_family=CanonicalActionFamily.EXTERNAL_HTTP,
        capability="external.local",
        logical_action_name="v11_external_http",
    )
    direct = agent_case("completion-direct", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE)
    internal = agent_case(
        "completion-internal", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE,
        placement="TRUSTED_MODULE_LOCAL",
    )
    outcomes = {}
    for gate, case, internal_path in (
        ("EXTERNAL_HTTP", external, False),
        ("DIRECT_AGENT_SERVICE", direct, False),
        ("TRUSTED_MODULE_LOCAL_AGENT", internal, True),
    ):
        try:
            outcome = (
                canonical_internal_outcome(case, OUTPUT / "raw" / gate.lower())
                if internal_path else
                canonical_external_outcome(case, OUTPUT / "raw" / gate.lower())
            )
            outcomes[gate] = outcome
            trace = outcome.evidence.get("raw_trace") or outcome.evidence.get("cover_trace")
            rows.append({
                "gate": gate, "functional": bool(outcome.result), "admitted": 1, "delivered": 1,
                "dummy_provider_operations": outcome.evidence["dummy_provider_operations"],
                "profile_overflow_events": trace["profile_overflow_events"], "error": "",
            })
        except Exception as error:
            rows.append({"gate": gate, "functional": False, "admitted": 1, "delivered": "",
                         "dummy_provider_operations": "", "profile_overflow_events": "",
                         "error": f"{type(error).__name__}: {error}"})

    early = with_readiness(tool_case("completion-early", "FRAMEWORK_NEUTRAL"), "EARLY_READY")
    late = with_readiness(
        replace(tool_case("completion-late", "FRAMEWORK_NEUTRAL"), operation_id="opcompletionlate"),
        "LATE_READY_WITHIN_BOUND",
    )
    try:
        pair = run_development_pair(early, late, OUTPUT / "raw" / "readiness")
        rows.append({
            "gate": "CONTROLLED_COMPLETION_BEHAVIOR", "functional": pair.functional,
            "admitted": 2, "delivered": 2,
            "dummy_provider_operations": pair.arm_a.evidence["dummy_provider_operations"] + pair.arm_b.evidence["dummy_provider_operations"],
            "profile_overflow_events": pair.arm_a.evidence["profile_overflow_events"] + pair.arm_b.evidence["profile_overflow_events"],
            "structural_equal": pair.structural_equal, "size_equal": pair.size_equal,
            "private_readiness_a_ms": 2, "private_readiness_b_ms": 30, "error": "",
        })
    except Exception as error:
        rows.append({"gate": "CONTROLLED_COMPLETION_BEHAVIOR", "functional": False, "admitted": 2,
                     "delivered": "", "dummy_provider_operations": "", "profile_overflow_events": "",
                     "error": f"{type(error).__name__}: {error}"})

    strict = {"both_functional": False, "structural_equal": False, "size_equal": False}
    if "TRUSTED_MODULE_LOCAL_AGENT" in outcomes and "DIRECT_AGENT_SERVICE" in outcomes:
        ip = public_projections(outcomes["TRUSTED_MODULE_LOCAL_AGENT"])
        ep = public_projections(outcomes["DIRECT_AGENT_SERVICE"])
        strict = {
            "both_functional": bool(outcomes["TRUSTED_MODULE_LOCAL_AGENT"].result) and bool(outcomes["DIRECT_AGENT_SERVICE"].result),
            "structural_equal": ip[0] == ep[0],
            "size_equal": ip[1] == ep[1],
            "internal_provider_invocations": outcomes["TRUSTED_MODULE_LOCAL_AGENT"].evidence["cover_trace"]["provider_invocations"],
            "external_provider_invocations": outcomes["DIRECT_AGENT_SERVICE"].evidence["raw_trace"]["provider_invocations"],
            "dummy_heavy_ops": outcomes["TRUSTED_MODULE_LOCAL_AGENT"].evidence["dummy_provider_operations"] + outcomes["DIRECT_AGENT_SERVICE"].evidence["dummy_provider_operations"],
        }
    (OUTPUT / "internal_external_strict.json").write_text(json.dumps(strict, indent=2) + "\n", encoding="utf-8")

    with (OUTPUT / "functional_matrix.csv").open("x", newline="", encoding="utf-8") as handle:
        fields = ["gate", "functional", "admitted", "delivered", "dummy_provider_operations",
                  "profile_overflow_events", "structural_equal", "size_equal",
                  "private_readiness_a_ms", "private_readiness_b_ms", "error"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "summary.json").write_text(json.dumps({
        "rows": len(rows), "passed": sum(str(row["functional"]).lower() == "true" for row in rows),
        "failed": [row for row in rows if str(row["functional"]).lower() != "true"],
        "strict": strict, "holdout_cases_executed": 0,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

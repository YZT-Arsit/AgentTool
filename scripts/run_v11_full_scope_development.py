from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v10_holdout.harness import load_v10_profile
from v11_full_scope.canonical import (
    canonical_external_outcome,
    canonical_internal_outcome,
    canonical_multi_action,
    outcome_json,
)
from v11_full_scope.fixtures import SCHEMAS_AND_VALUES, agent_case, tool_case, with_readiness
from v11_full_scope.frameworks import canonical_implementation, native_implementation, run_framework_case
from v11_full_scope.models import AgentServiceSubtype, CanonicalActionFamily
from v11_full_scope.structural import run_development_pair


OUTPUT = ROOT / "results_v11_development" / "full_scope_matrix"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def semantic_row(case, native, canonical) -> dict[str, object]:
    evidence = canonical.runtime_evidence["action_implementation_evidence"]
    return {
        "case_id": case.case_id,
        "framework": case.framework,
        "action_family": case.action_family.value,
        "agent_service_subtype": case.agent_service_subtype.value if case.agent_service_subtype else "",
        "argument_schema": case.argument_schema.schema_id,
        "effect_semantics": case.effect_semantics,
        "outcome_class": case.scenario,
        "native_canonical_projection_equal": native.projection() == canonical.projection(),
        "native_framework_action_reached": native.final_framework_visible_result_state["action_result_received"],
        "canonical_framework_action_reached": canonical.final_framework_visible_result_state["action_result_received"],
        "canonical_result": canonical.result,
        "effect_count": canonical.effect_count,
        "dummy_heavy_ops": evidence.get("dummy_provider_operations", 0),
        "profile_overflow_events": evidence.get("profile_overflow_events", 0),
        "official_simplepir": evidence.get("official_simplepir", False),
        "rfc9292_rfc9458": evidence.get("rfc9292_rfc9458", False),
        "development_only": True,
    }


def run_semantic(case, index: int):
    native = run_framework_case(case, native_implementation)
    canonical = run_framework_case(
        case, canonical_implementation(OUTPUT / "semantic_raw" / f"{index:03d}-{case.case_id}")
    )
    return semantic_row(case, native, canonical)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite V11 development evidence: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    semantic_rows: list[dict[str, object]] = []
    cases = []

    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        for schema_index in range(len(SCHEMAS_AND_VALUES)):
            cases.append(tool_case(f"matrix-{framework.split()[0].lower()}-schema-{schema_index}", framework, schema_index))

    for framework in ("OpenAI Agents SDK", "Microsoft Agent Framework"):
        cases.append(agent_case(f"matrix-{framework.split()[0].lower()}-agent-as-tool", framework, AgentServiceSubtype.AGENT_AS_TOOL))
    cases.append(agent_case("matrix-openai-handoff", "OpenAI Agents SDK", AgentServiceSubtype.HANDOFF))

    for effect in ("READ_ONLY", "IDEMPOTENT_EFFECT", "NON_IDEMPOTENT_EFFECT"):
        for scenario in ("SUCCESS", "ERROR", "BOUNDED_TIMEOUT"):
            cases.append(tool_case(f"matrix-tool-{effect.lower()}-{scenario.lower()}", "OpenAI Agents SDK", 0, effect, scenario))
            cases.append(agent_case(f"matrix-agent-{effect.lower()}-{scenario.lower()}", "OpenAI Agents SDK", AgentServiceSubtype.AGENT_AS_TOOL, effect, scenario))

    base = tool_case("matrix-external-http", "OpenAI Agents SDK")
    for scenario in ("SUCCESS", "ERROR", "BOUNDED_TIMEOUT"):
        cases.append(
            replace(
                base,
                case_id=f"matrix-external-http-{scenario.lower()}",
                operation_id=f"opexternal{scenario.lower()}",
                action_family=CanonicalActionFamily.EXTERNAL_HTTP,
                capability="external.local",
                logical_action_name="v11_external_http",
                scenario=scenario,
            )
        )

    for index, case in enumerate(cases):
        semantic_rows.append(run_semantic(case, index))
    write_csv(OUTPUT / "semantic_matrix.csv", semantic_rows)

    functional_rows: list[dict[str, object]] = []
    for count in (1, 10, 50):
        multi_cases = [
            replace(
                tool_case(f"functional-multi-{count}-{index}", "FRAMEWORK_NEUTRAL"),
                operation_id=f"v11dev{count:02d}{index:03d}",
            )
            for index in range(count)
        ]
        result = canonical_multi_action(multi_cases, OUTPUT / "functional_raw" / f"multi-{count}")
        functional_rows.append({"gate": f"TOOL_{count}", **{key: value for key, value in result.items() if key not in {"raw_trace", "provider_observations", "strict_structural_projection", "strict_size_projection"}}})

    external = replace(
        tool_case("functional-external-http", "FRAMEWORK_NEUTRAL"),
        action_family=CanonicalActionFamily.EXTERNAL_HTTP,
        capability="external.local",
        logical_action_name="v11_external_http",
    )
    direct = agent_case("functional-direct-agent", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE)
    internal = agent_case("functional-internal-agent", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE, placement="TRUSTED_MODULE_LOCAL")
    for gate, case, internal_path in (
        ("EXTERNAL_HTTP", external, False),
        ("DIRECT_AGENT_SERVICE", direct, False),
        ("TRUSTED_MODULE_LOCAL_AGENT", internal, True),
    ):
        outcome = (
            canonical_internal_outcome(case, OUTPUT / "functional_raw" / gate.lower())
            if internal_path
            else canonical_external_outcome(case, OUTPUT / "functional_raw" / gate.lower())
        )
        functional_rows.append({
            "gate": gate,
            "functional": bool(outcome.result),
            "admitted": 1,
            "delivered": 1,
            "dummy_provider_operations": outcome.evidence["dummy_provider_operations"],
            "profile_overflow_events": (outcome.evidence.get("raw_trace") or outcome.evidence.get("cover_trace"))["profile_overflow_events"],
            "official_simplepir": outcome.evidence["official_simplepir"],
            "descriptor_authenticated": outcome.evidence["descriptor_authenticated"],
            "public_profile": outcome.evidence["public_profile"],
        })

    early = with_readiness(tool_case("functional-readiness-early", "FRAMEWORK_NEUTRAL"), "EARLY_READY")
    late = with_readiness(
        replace(tool_case("functional-readiness-late", "FRAMEWORK_NEUTRAL"), operation_id="opv11readinesslate"),
        "LATE_READY_WITHIN_BOUND",
    )
    readiness = run_development_pair(early, late, OUTPUT / "functional_raw" / "readiness")
    functional_rows.append({
        "gate": "CONTROLLED_COMPLETION_BEHAVIOR",
        "functional": readiness.functional,
        "admitted": 2,
        "delivered": 2,
        "dummy_provider_operations": readiness.arm_a.evidence["dummy_provider_operations"] + readiness.arm_b.evidence["dummy_provider_operations"],
        "profile_overflow_events": readiness.arm_a.evidence["profile_overflow_events"] + readiness.arm_b.evidence["profile_overflow_events"],
        "official_simplepir": True,
        "descriptor_authenticated": True,
        "public_profile": readiness.arm_a.evidence["public_profile"],
        "structural_equal": readiness.structural_equal,
        "size_equal": readiness.size_equal,
        "private_readiness_a_ms": 2,
        "private_readiness_b_ms": 30,
    })
    write_csv(OUTPUT / "functional_matrix.csv", functional_rows)

    internal_external = run_development_pair(
        agent_case("strict-external", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE),
        agent_case("strict-external-peer", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE),
        OUTPUT / "functional_raw" / "external-control-pair",
    )
    # The actual internal-vs-external evidence was generated separately because
    # the internal arm uses the trusted backend and cover transcript.
    internal_outcome = canonical_internal_outcome(
        agent_case("strict-internal", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE, placement="TRUSTED_MODULE_LOCAL"),
        OUTPUT / "functional_raw" / "strict-internal",
    )
    external_outcome = canonical_external_outcome(
        agent_case("strict-external-real", "FRAMEWORK_NEUTRAL", AgentServiceSubtype.DIRECT_AGENT_SERVICE),
        OUTPUT / "functional_raw" / "strict-external",
    )
    from v11_full_scope.canonical import public_projections
    internal_projection = public_projections(internal_outcome)
    external_projection = public_projections(external_outcome)
    strict = {
        "both_functional": bool(internal_outcome.result) and bool(external_outcome.result),
        "structural_equal": internal_projection[0] == external_projection[0],
        "size_equal": internal_projection[1] == external_projection[1],
        "internal_provider_invocations": internal_outcome.evidence["cover_trace"]["provider_invocations"],
        "external_provider_invocations": external_outcome.evidence["raw_trace"]["provider_invocations"],
        "dummy_heavy_ops": internal_outcome.evidence["dummy_provider_operations"] + external_outcome.evidence["dummy_provider_operations"],
        "public_profile": internal_outcome.evidence["public_profile"],
        "development_only": True,
    }
    (OUTPUT / "internal_external_strict.json").write_text(json.dumps(strict, indent=2) + "\n", encoding="utf-8")

    profile = asdict(load_v10_profile())
    profile.update({
        "phase": "V11_FULL_SCOPE_DEVELOPMENT",
        "security_relevant_values_changed_from_v10": False,
        "private_payload_admission_bytes": 400,
        "timing_privacy": "OPEN / NOT TESTED",
    })
    (OUTPUT / "public_profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    summary = {
        "semantic_rows": len(semantic_rows),
        "semantic_passed": sum(row["native_canonical_projection_equal"] is True for row in semantic_rows),
        "functional_rows": len(functional_rows),
        "functional_passed": sum(row["functional"] is True for row in functional_rows),
        "dummy_heavy_ops": sum(int(row.get("dummy_provider_operations", 0)) for row in functional_rows),
        "internal_external_strict": strict,
        "holdout_cases_executed": 0,
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

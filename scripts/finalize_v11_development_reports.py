from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SEMANTIC_SOURCE = ROOT / "results_v11_development" / "full_scope_matrix" / "semantic_matrix.csv"
FUNCTIONAL_SOURCE = ROOT / "results_v11_development" / "functional_completion_run2" / "functional_matrix.csv"
STRICT_SOURCE = ROOT / "results_v11_development" / "functional_completion_run2" / "internal_external_strict.json"
OLD_MANIFESTS = (
    "CANONICAL_SEMANTIC_HOLDOUT_V10_FREEZE.json",
    "STRUCTURAL_SIZE_HOLDOUT_V10_FREEZE.json",
    "CANONICAL_SEMANTIC_HOLDOUT_V10_1_FREEZE.json",
    "STRUCTURAL_SIZE_HOLDOUT_V10_1_FREEZE.json",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: str, text: str) -> None:
    target = ROOT / path
    if target.exists():
        raise FileExistsError(f"refusing report overwrite: {target}")
    target.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: str, rows: list[dict[str, object]]) -> None:
    target = ROOT / path
    if target.exists():
        raise FileExistsError(f"refusing report overwrite: {target}")
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with target.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, object]], keys: list[str]) -> str:
    return "\n".join(
        ["| " + " | ".join(keys) + " |", "| " + " | ".join("---" for _ in keys) + " |"]
        + ["| " + " | ".join(str(row.get(key, "")).replace("|", "\\|") for key in keys) + " |" for row in rows]
    )


def supersession() -> None:
    hashes = {name: sha(ROOT / name) for name in OLD_MANIFESTS}
    semantic_sites: set[str] = set()
    structural_sequences: list[dict[str, object]] = []
    for name in OLD_MANIFESTS:
        value = json.loads((ROOT / name).read_text(encoding="utf-8"))
        if "cases" in value:
            for case in value["cases"]:
                source = case.get("source", {})
                semantic_sites.add(json.dumps(source, sort_keys=True))
        if "pairs" in value:
            for pair in value["pairs"]:
                structural_sequences.append({
                    "origin": name,
                    "pair_id": pair.get("pair_id"),
                    "stratum": pair.get("stratum"),
                    "arms": pair.get("arms"),
                })
    exclusion = {
        "schema": "AgentTool.V11FutureExclusionSet/1",
        "status": "FROZEN_NOT_EXECUTED_SUPERSEDED_BY_FULL_SCOPE_V11",
        "old_manifest_hashes": hashes,
        "semantic_source_sites": [json.loads(value) for value in sorted(semantic_sites)],
        "structural_private_sequences": structural_sequences,
        "runtime_outcomes_observed": False,
    }
    write("V11_FUTURE_EXCLUSION_SET.json", json.dumps(exclusion, indent=2, sort_keys=True))
    rows = [{"manifest": key, "sha256": value} for key, value in hashes.items()]
    write(
        "V10_V10_1_SUPERSESSION_V11.md",
        "# V10/V10.1 supersession audit\n\n"
        "Permanent status: `FROZEN_NOT_EXECUTED_SUPERSEDED_BY_FULL_SCOPE_V11`. "
        "The four manifests were read only for hashing and future exclusion construction. No selected case or arm entered an executing function; selected runtime outcomes remain unknown.\n\n"
        + markdown_table(rows, ["manifest", "sha256"])
        + f"\n\nExcluded source-site records: **{len(semantic_sites)}**. Excluded structural sequences: **{len(structural_sequences)}**. "
        "The exact records are in `V11_FUTURE_EXCLUSION_SET.json`."
    )


def coverage() -> None:
    corpus = list(csv.DictReader((ROOT / "ACTION_MEDIATION_CORPUS_V6.csv").open(encoding="utf-8")))
    action = [row for row in corpus if row["v6_disposition"] in {"MEDIATED", "PARTIAL", "UNSUPPORTED"}]
    counts = Counter(row["v6_disposition"] for row in action)
    framework = Counter((row["framework"], row["v6_disposition"]) for row in action)
    rows = []
    for phase in ("V6_FROZEN_BASELINE", "V11_DEVELOPMENT_RECOMPUTE"):
        for disposition in ("MEDIATED", "PARTIAL", "UNSUPPORTED"):
            rows.append({
                "phase": phase, "frozen_denominator": len(action), "disposition": disposition,
                "count": counts[disposition], "fraction": f"{counts[disposition] / len(action):.6f}",
                "openai": framework[("OpenAI Agents SDK", disposition)],
                "microsoft": framework[("Microsoft Agent Framework", disposition)],
                "rule": "exact frozen V6 source-site disposition; no untested source site relabeled",
            })
    write_csv("ACTION_MEDIATION_COVERAGE_V11.csv", rows)
    write(
        "ACTION_MEDIATION_COVERAGE_V11.md",
        "# Action mediation coverage V11\n\n"
        "The denominator remains exactly **1,370**. V11 generic development adapters establish family-level feasibility, but they do not mechanically prove new exact source sites in the frozen corpus. Therefore no source site was manually relabeled.\n\n"
        + markdown_table(rows, ["phase", "disposition", "count", "fraction", "openai", "microsoft"])
        + "\n\nResult: **894 MEDIATED / 473 PARTIAL / 3 UNSUPPORTED**. This deliberately preserves the negative MCP/callback evidence."
    )
    partial = list(csv.DictReader((ROOT / "ACTION_MEDIATION_PARTIAL_PARETO_V7.csv").open(encoding="utf-8")))
    out = []
    for row in partial:
        out.append({
            **row,
            "v11_before": "PARTIAL",
            "v11_after": "PARTIAL",
            "v11_reason": "V11 did not implement and semantically test this exact frozen MCP/hosted source family",
        })
    write_csv("ACTION_MEDIATION_PARTIAL_REASONS_V11.csv", out)


def matrices() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    semantic = list(csv.DictReader(SEMANTIC_SOURCE.open(encoding="utf-8")))
    functional = list(csv.DictReader(FUNCTIONAL_SOURCE.open(encoding="utf-8")))
    shutil.copyfile(SEMANTIC_SOURCE, ROOT / "FULL_SCOPE_SEMANTIC_DEVELOPMENT_V11.csv")
    shutil.copyfile(SEMANTIC_SOURCE, ROOT / "SEMANTIC_EXECUTOR_MATRIX_V11.csv")
    shutil.copyfile(FUNCTIONAL_SOURCE, ROOT / "FULL_SCOPE_FUNCTIONAL_RESULTS_V11.csv")
    effect_rows = [
        row for row in semantic
        if row["outcome_class"] in {"SUCCESS", "ERROR", "BOUNDED_TIMEOUT"}
        and row["effect_semantics"] in {"READ_ONLY", "IDEMPOTENT_EFFECT", "NON_IDEMPOTENT_EFFECT"}
    ]
    write_csv("EFFECT_SEMANTICS_MATRIX_V11.csv", effect_rows)
    semantic_pass = sum(row["native_canonical_projection_equal"] == "True" for row in semantic)
    write(
        "SEMANTIC_EXECUTOR_MATRIX_V11.md",
        "# Semantic executor matrix V11\n\n"
        f"All **{semantic_pass}/{len(semantic)}** executed development rows produced equal independently generated native and canonical semantic projections. "
        "These are Level A action-boundary results, not untouched source-body execution.\n\n"
        + markdown_table(semantic, ["framework", "action_family", "agent_service_subtype", "argument_schema", "effect_semantics", "outcome_class", "native_canonical_projection_equal"])
    )
    write(
        "EFFECT_SEMANTICS_MATRIX_V11.md",
        "# Effect semantics matrix V11\n\n"
        "Executed local development cases cover success, provider error, and bounded timeout for TOOL, AGENT_SERVICE/AGENT_AS_TOOL, and the READ_ONLY EXTERNAL_HTTP route. "
        "The frozen external HTTP route has no effectful variant. NON_IDEMPOTENT timeout is reported as `EFFECT_OUTCOME_UNKNOWN`, never as exactly-once success/failure.\n\n"
        + markdown_table(effect_rows, ["action_family", "agent_service_subtype", "effect_semantics", "outcome_class", "effect_count", "native_canonical_projection_equal"])
    )
    write(
        "FULL_SCOPE_SEMANTIC_DEVELOPMENT_V11.md",
        "# Full-scope semantic development V11\n\n"
        f"Result: **{semantic_pass}/{len(semantic)} PASS** on non-holdout fixtures. Framework-native evidence used actual OpenAI FunctionTool/Agent.as_tool/handoff paths and Microsoft FunctionInvocationLayer/Agent.as_tool. "
        "Microsoft handoff was not represented because the optional orchestrations mechanism is absent from the pinned snapshot."
    )
    functional_pass = sum(row["functional"] == "True" for row in functional)
    write(
        "FULL_SCOPE_FUNCTIONAL_REPORT_V11.md",
        "# Full-scope functional report V11\n\n"
        f"Run-2 result: **{functional_pass}/{len(functional)} gates passed**. The 1-action run had a provider result durably committed but not delivered after a ~737 ms first-round stall exceeded the frozen 555 ms session. "
        "The same gate passed in the pytest development suite, while 10 and 50 actions passed in run 2. This is preserved as intermittent controlled-host/session-budget instability, so MULTI_ACTION is PARTIAL rather than promoted to PASS.\n\n"
        + markdown_table(functional, ["gate", "functional", "admitted", "delivered", "dummy_provider_operations", "profile_overflow_events", "error"])
    )
    return semantic, functional


def docs(semantic: list[dict[str, str]], functional: list[dict[str, str]]) -> None:
    strict = json.loads(STRICT_SOURCE.read_text(encoding="utf-8"))
    profile = json.loads((ROOT / "PUBLIC_PROFILE_V10.json").read_text(encoding="utf-8"))
    profile.update({
        "phase": "V11_FULL_SCOPE_DEVELOPMENT",
        "security_relevant_values_changed_from_v10": False,
        "private_action_payload_admission_bytes": 400,
        "oversize_policy": "FAIL_CLOSED_WITHOUT_RESIZING_PUBLIC_PROFILE",
        "timing_privacy": "OPEN / NOT TESTED",
    })
    write("PUBLIC_PROFILE_DEVELOPMENT_V11.json", json.dumps(profile, indent=2))
    write("FULL_CANONICAL_ACTION_MODEL_V11.md", """# Full canonical action model V11

Private action families are `TOOL`, `EXTERNAL_HTTP`, and `AGENT_SERVICE`. Framework constructs map mechanically: ordinary Tool to TOOL; external HTTP to EXTERNAL_HTTP; direct Agent service, Agent-as-Tool, and handoff to AGENT_SERVICE with a private subtype. The public path remains one SimplePIR-selected authenticated descriptor, trusted authorization/route resolution, RFC 9292 BHTTP inside RFC 9458 OHTTP, one local Relay/Gateway endpoint class, and the frozen fixed-capacity transcript.

No Agent Control IR, whole-program compiler, ORAM invocation path, public subtype endpoint, or third-party network service was added. The trusted-module-local branch executes locally but emits the same OHTTP NOOP/WAIT cover schedule.
""")
    write("AGENT_SERVICE_SUBTYPE_V11.md", """# Private Agent-service subtype V11

Allowed encrypted inner values are `DIRECT_AGENT_SERVICE`, `AGENT_AS_TOOL`, and `HANDOFF`. `PrivateAgentServiceEnvelope` includes version, subtype, validated arguments, and bounded continuation data. Relay public evidence is checked against subtype, logical action, operation ID, and capability strings. All use the same `REAL_AGENT_SERVICE` Gateway route class and public endpoint.

The frozen 1024-byte BHTTP request bucket is unchanged. A conservative 400-byte private application-payload admission bound is enforced. A 372-byte near-bound envelope passed at 1079 final OHTTP bytes; a 628-byte envelope was rejected before execution instead of resizing the public profile.
""")
    write("STRUCTURED_TOOL_ARGUMENTS_V11.md", """# Structured Tool arguments V11

One generic schema-driven adapter was exercised through both pinned frameworks for: one string, integer, boolean, optional string, two primitives, three primitives, and one bounded object `{label:string,count:int,enabled:bool}`. The adapter creates the callable mechanically before execution and validates exact keys/types. Results: 14/14 native-vs-canonical schema rows passed.

This is bounded development support, not arbitrary Python signature or source-body support. Oversize private payloads fail closed under the frozen public bucket.
""")
    write("OPENAI_AGENT_AS_TOOL_V11.md", """# OpenAI Agent-as-Tool V11

The native development reference instantiates a child `Agent` and uses its actual `Agent.as_tool()` mechanism. The canonical implementation intercepts at the child Agent boundary, maps to private `AGENT_SERVICE/AGENT_AS_TOOL`, performs real SimplePIR and the accepted BHTTP/OHTTP/Relay/Gateway path, and returns the result through the parent framework Tool-result machinery. Runtime evidence confirms one child invocation and no direct remote child execution on the canonical path. Native/canonical projection equality passed.
""")
    write("OPENAI_HANDOFF_V11.md", """# OpenAI handoff V11

The native reference uses the pinned SDK's actual `agents.handoff` object, reaches one `HandoffOutputItem`, and ends with the target as `last_agent`. The canonical implementation maps target activation to private `AGENT_SERVICE/HANDOFF`, uses the accepted transport path, and returns the target result through handoff machinery without directly executing a remote target in the parent process. Projection equality passed.
""")
    write("MICROSOFT_AGENT_COMPOSITION_V11.md", """# Microsoft Agent composition V11

The pinned core snapshot exposes `Agent.as_tool()`. Native and canonical development executors used that actual API and passed semantic projection equality. The canonical child boundary uses `AGENT_SERVICE/AGENT_AS_TOOL` and the common external path.

The pinned core only lazily imports handoff/orchestration support from optional `agent-framework-orchestrations`; that package is not installed and its source is not present in the pinned tree. Status: `FRAMEWORK_NATIVE_MECHANISM_ABSENT`. No substitute API was invented.
""")
    write("INTERNAL_TRUSTED_AGENT_PATH_V11.md", """# Internal trusted Agent path V11

`LocalTrustedBackendV11` implements the vendor-neutral trusted execution interface for development only. Real SimplePIR selects an authenticated `AgentDescriptorV7` whose placement is `TRUSTED_MODULE_LOCAL`; execution occurs inside the local trusted abstraction. The simultaneously executed canonical public session contains only NOOP/WAIT cover traffic and caused zero provider invocations and zero dummy heavy operations.

This is not a hardware TEE, attestation, malicious-host timing protection, or rollback protection result.
""")
    write("INTERNAL_EXTERNAL_STRICT_PRECHECK_V11.md", "# STRICT internal/external development precheck\n\n" + markdown_table([strict], list(strict)) + "\n\nBoth arms were functional. Actual Relay-derived structural and size projections were exactly equal; timestamps were excluded. Internal provider invocations were zero and external provider invocations were one.")
    write("INTERNAL_RESULT_MULTIPLEXER_V11.md", """# Internal result multiplexer V11

`PrivateResultMultiplexer` accepts fixed logical results from `LOCAL_TRUSTED_RESULT` or `OHTTP_GATEWAY_RESULT`, rejects duplicate submissions/unknown sources, and delivers through the existing trusted `DeliveryLedger`. Replay suppression is tested. The documented non-atomic framework-callback versus durable `FRAMEWORK_DELIVERED` update remains PARTIAL; no general exactly-once claim is made.
""")
    write("STRUCTURAL_GENERATOR_VALIDATION_V11.md", """# Structural generator validation V11

The validator mechanically constructs a `ProtectedActionIntent`, obtains the authenticated canonical descriptor, invokes the frozen trusted resolver, and compares manifest effect semantics with the resolved route. `tool.a/READ_ONLY` and `tool.b/IDEMPOTENT_EFFECT` pass; the old `tool.b/READ_ONLY` design fails closed. No selected structural holdout was loaded or executed.
""")
    write("COMPLETION_BEHAVIOR_DEVELOPMENT_V11.md", """# Completion behavior development V11

The private provider-readiness classes are `EARLY_READY=2 ms` and `LATE_READY_WITHIN_BOUND=30 ms`, both below the unchanged public 50 ms completion bound. Both arms used the same Agent/action/profile; actual strict structural and size projections were equal and both arms were functional. Completion only publishes a private ready result. Timing privacy was not tested.
""")
    write_csv("SOURCE_BODY_EXECUTABLE_SUBSET_V11.csv", [{"level": "B_SOURCE_BODY", "executable_cases": 0, "status": "NOT_IMPLEMENTED", "reason": "V11 implemented generic Level-A framework action-boundary adapters only"}])
    write("SOURCE_BODY_EXECUTABLE_SUBSET_V11.md", "# Source-body executable subset V11\n\nExact count: **0**. V11 did not execute original source Tool/Agent bodies. All 38 semantic rows are explicitly Level A action-boundary fidelity using deterministic local providers. This negative boundary is preserved.")

    write("CURRENT_SECURITY_MATRIX_V11.md", """# Current security matrix V11

| Property | Status | Evidence boundary |
| --- | --- | --- |
| Native/canonical Level-A semantics | PASS | 38/38 non-holdout rows |
| RFC 9292/9458 fixed structure/size | PASS (development) | actual Relay projections |
| Internal/external STRICT structure/size | PASS (development) | one paired precheck |
| Dummy heavy work | PASS | 0 |
| Multi-action/session reliability | PARTIAL | 10/50 pass; one intermittent 1-action budget failure |
| Source-body semantics | NOT IMPLEMENTED | exact subset 0 |
| Timing privacy | OPEN / NOT TESTED | timestamps not classified |
| Packet-level timing | OPEN | not evaluated |
| Hardware TEE | NOT TESTED | local software backend only |
| Final holdout | NOT RUN | all V10/V10.1 outcomes remain unknown |
""")
    write("FINAL_FULL_SCOPE_DEVELOPMENT_AUDIT_V11.md", """# Final full-scope development audit V11

## Decision

V11 establishes the intended canonical action-family semantics and internal/external structural design at development level, but the executor is **not ready to freeze**. One fresh functional development run lost delivery of a durably committed single result when a first-round controlled-host stall exceeded the unchanged 555 ms public session. Earlier executions of the same gate passed, so this is intermittent rather than a deterministic semantic mismatch; it nevertheless prevents declaring the complete harness stable.

## Supported development claims

- 38/38 framework-native versus canonical Level-A semantic projections matched.
- OpenAI Function Tool, Agent-as-Tool, and handoff use actual pinned APIs.
- Microsoft Tool and Agent-as-Tool use actual pinned APIs; handoff is absent.
- Seven bounded structured schemas pass in both frameworks.
- Real SimplePIR, authenticated descriptors, trusted routing, BHTTP, OHTTP, Relay, Gateway, DeliveryLedger, internal cover, and result multiplexing were exercised locally.
- STRICT internal/external public structural and size projections match; dummy heavy operations are zero.

## Preserved limitations

- No V10/V10.1 selected outcome was observed.
- Corpus coverage remains 894/473/3; family feasibility does not relabel exact source sites.
- Source-body subset is 0.
- Timing, packet timing, and hardware TEE remain open/not tested.
- Multi-action/session-budget stability is PARTIAL, so `ORIGINAL_SOFTWARE_DESIGN_SCOPE_COMPLETE=NO` and `READY_FOR_V11A_FRESH_HOLDOUT_FREEZE=NO`.
""")


def freeze_manifest() -> None:
    files = [
        *sorted((ROOT / "v11_full_scope").glob("*.py")),
        ROOT / "tests" / "test_v11_full_scope.py",
        ROOT / "scripts" / "run_v11_full_scope_development.py",
        ROOT / "scripts" / "run_v11_functional_completion.py",
        ROOT / "scripts" / "finalize_v11_development_reports.py",
        ROOT / "PUBLIC_PROFILE_V10.json",
        ROOT / "common_action_gateway_v2" / "bin" / "canonical-v9-runner.exe",
    ]
    manifest = {
        "schema": "AgentTool.V11ExecutionHarnessFreeze/1",
        "phase": "V11_FULL_SCOPE_DEVELOPMENT",
        "status": "NOT_FROZEN_DEVELOPMENT_GATE_INCOMPLETE",
        "reason": "intermittent public-session budget/delivery failure in development evidence",
        "holdout_selected": False,
        "holdout_executed": False,
        "source_hashes_snapshot_not_an_execution_freeze": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha(path) for path in files
        },
        "ready_for_v11a": False,
    }
    write("V11_EXECUTION_HARNESS_FREEZE.json", json.dumps(manifest, indent=2, sort_keys=True))


def main() -> None:
    supersession()
    coverage()
    semantic, functional = matrices()
    docs(semantic, functional)
    freeze_manifest()


if __name__ == "__main__":
    main()

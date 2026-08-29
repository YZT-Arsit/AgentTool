"""Decompose V6 PARTIAL action sites without relabeling unsupported behavior."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ACTION_MEDIATION_CORPUS_V6.csv"


def family(row: dict[str, str]) -> tuple[str, str, str]:
    detail = row["detail"].lower()
    path = row["relative_path"].lower()
    if "hosted_mcp" in path or "hostedmcptool" in detail or "mcptoolchoice" in detail:
        return (
            "HOSTED_PROVIDER_MCP",
            "PARTIAL",
            "provider-hosted invocation would require a common provider-facing action hook before named activation",
        )
    invocation_tokens = (
        "mcptool", "mcpstdiotool", "mcpstreamablehttptool", "mcpwebsockettool",
        "connectedmcptool", "call_tool", "mcp.run", "to_function_approval_response",
        "wrap_mcp_function", "make_connected_mcp_tool",
    )
    if any(token in detail for token in invocation_tokens):
        return (
            "MCP_INVOCATION_OR_APPROVAL",
            "PARTIAL",
            "a generic framework MCP call/approval adapter appears plausible but is not yet integrated and semantically tested",
        )
    if any(token in detail for token in ("mcpserver", "mcp_servers", "mcpmanager", "mcpskills", "mcpskill")):
        return (
            "MCP_SERVER_DISCOVERY_OR_SKILL_CATALOG",
            "PARTIAL",
            "server discovery and skill catalogs mix control metadata with eventual actions; exact action-boundary lowering is unproven",
        )
    if any(token in detail for token in ("result", "content", "parse", "prepare", "stamp", "normalize", "timedelta", "error", "span")):
        return (
            "MCP_RESULT_CONTENT_OR_HELPER",
            "PARTIAL",
            "helper/result sites were conservatively action-relevant in V6; source-local evidence is insufficient to relabel them",
        )
    return (
        "MCP_OTHER_UNPROVEN",
        "PARTIAL",
        "no generic, exact, tested interception contract was demonstrated",
    )


def main() -> None:
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8", newline="")))
    partial = [row for row in rows if row["v6_disposition"] == "PARTIAL"]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    metadata: dict[str, tuple[str, str]] = {}
    for row in partial:
        name, disposition, requirement = family(row)
        grouped[name].append(row)
        metadata[name] = disposition, requirement

    output_rows = []
    for name, members in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        frameworks = Counter(row["framework"] for row in members)
        examples = "; ".join(
            f"{row['framework']}:{row['relative_path']}:{row['line']}:{row['detail']}"
            for row in members[:3]
        )
        output_rows.append({
            "family": name,
            "instances": len(members),
            "source_files": len({(row["framework"], row["relative_path"]) for row in members}),
            "openai_instances": frameworks["OpenAI Agents SDK"],
            "microsoft_instances": frameworks["Microsoft Agent Framework"],
            "v7_disposition": metadata[name][0],
            "exact_lowering_requirement": metadata[name][1],
            "representative_source_traceable_examples": examples,
        })
    assert sum(int(row["instances"]) for row in output_rows) == 473
    csv_path = ROOT / "ACTION_MEDIATION_PARTIAL_PARETO_V7.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    report = [
        "# Action Mediation PARTIAL Pareto V7",
        "",
        "This is a decomposition of the frozen 473 V6 `PARTIAL` instances. No",
        "instance is relabeled, and no hypothetical coverage is counted.",
        "",
        "| Family | Instances | Files | OpenAI | Microsoft | V7 status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in output_rows:
        report.append(
            f"| {row['family']} | {row['instances']} | {row['source_files']} | "
            f"{row['openai_instances']} | {row['microsoft_instances']} | {row['v7_disposition']} |"
        )
    report += [
        "",
        "## Interpretation",
        "",
        "The Pareto is dominated by MCP-related source sites, but the frozen corpus",
        "mixes actual invocation/approval seams, hosted-provider activation, discovery,",
        "content conversion, and helper code. A small generic hook may cover the first",
        "category; it cannot honestly cover the others without framework-contract and",
        "runtime semantic tests. V7 therefore preserves all 473 as PARTIAL.",
        "",
        "The exact source-traceable examples and required lowering contracts are in the CSV.",
    ]
    (ROOT / "ACTION_MEDIATION_PARTIAL_PARETO_V7.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    counts = Counter(row["v6_disposition"] for row in rows)
    coverage_rows = [
        {
            "version": "V6",
            "frozen_total_behavior_instances": 7386,
            "action_relevant_denominator": 1370,
            "mediated": counts["MEDIATED"],
            "partial": counts["PARTIAL"],
            "unsupported": counts["UNSUPPORTED"],
            "fully_mediated_fraction": f"{counts['MEDIATED'] / 1370:.6f}",
            "status": "FROZEN",
        },
        {
            "version": "V7",
            "frozen_total_behavior_instances": 7386,
            "action_relevant_denominator": 1370,
            "mediated": counts["MEDIATED"],
            "partial": counts["PARTIAL"],
            "unsupported": counts["UNSUPPORTED"],
            "fully_mediated_fraction": f"{counts['MEDIATED'] / 1370:.6f}",
            "status": "NO_UNTESTED_RELABELING",
        },
    ]
    with (ROOT / "ACTION_MEDIATION_COVERAGE_V7.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(coverage_rows[0]))
        writer.writeheader()
        writer.writerows(coverage_rows)
    (ROOT / "ACTION_MEDIATION_COVERAGE_V7.md").write_text(
        "# Action Mediation Coverage V7\n\n"
        "The frozen corpus remains 7,386 behavior instances and the action-relevant "
        "denominator remains 1,370.\n\n"
        "- V6: **894/1,370 = 65.26%** fully mediated; 473 PARTIAL; 3 UNSUPPORTED.\n"
        "- V7: **894/1,370 = 65.26%** fully mediated; 473 PARTIAL; 3 UNSUPPORTED.\n\n"
        "No generic MCP hook was counted because no hook was both integrated into the "
        "two pinned framework runtimes and semantically tested in this closure stage. "
        "The separate historical IR-v1 3,574/7,386 = 48.39% baseline is unchanged.\n",
        encoding="utf-8",
    )
    print(f"decomposed {len(partial)} PARTIAL instances into {len(output_rows)} families")


if __name__ == "__main__":
    main()

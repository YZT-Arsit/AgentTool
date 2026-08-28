from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "CORPUS_BEHAVIOR_INSTANCES.csv"
OUTPUT = ROOT / "ACTION_MEDIATION_CORPUS_V6.csv"

MEDIATED = {"tool", "agents_as_tools", "handoff"}
PARTIAL = {"mcp_tool_boundary"}
UNSUPPORTED = {"conditional_handoff_callback"}


def status(kind: str) -> tuple[str, str]:
    if kind in MEDIATED:
        return "MEDIATED", "native function-Tool/Agent-as-Tool/handoff action seam is interceptable"
    if kind in PARTIAL:
        return "PARTIAL", "MCP expansion is mediated after materialization; hosted/transport-specific paths need adapter proof"
    if kind in UNSUPPORTED:
        return "UNSUPPORTED", "callback-selected handoff requires a framework-specific post-selection hook"
    return "NOT_ACTION_RELEVANT", "internal reasoning/control behavior does not itself escape the outbound action boundary"


def main() -> None:
    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8")))
    out: list[dict[str, str]] = []
    for row in rows:
        disposition, reason = status(row["behavior_kind"])
        out.append({
            "corpus_version": "IR-v1-frozen-membership-action-audit-v6",
            "framework": row["framework"], "pinned_commit": row["pinned_commit"],
            "relative_path": row["relative_path"], "line": row["line"],
            "action_site_kind": row["behavior_kind"], "detail": row["detail"],
            "v6_disposition": disposition, "reason": reason,
        })
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out[0]))
        writer.writeheader(); writer.writerows(out)
    relevant = [row for row in out if row["v6_disposition"] != "NOT_ACTION_RELEVANT"]
    counts = Counter(row["v6_disposition"] for row in out)
    framework = Counter((row["framework"], row["v6_disposition"]) for row in relevant)
    summary = {
        "identical_frozen_files": len(list(csv.DictReader((ROOT / "CORPUS_MANIFEST.csv").open(encoding="utf-8")))),
        "identical_frozen_behavior_instances": len(out), "action_relevant_instances": len(relevant),
        "counts": dict(counts), "fully_mediated_fraction": counts["MEDIATED"] / len(relevant),
        "mediated_or_partial_fraction": (counts["MEDIATED"] + counts["PARTIAL"]) / len(relevant),
        "framework_counts": {f"{key[0]}|{key[1]}": value for key, value in sorted(framework.items())},
        "interpretation": "static source-traceable action-boundary audit, not runtime semantic proof",
    }
    (ROOT / "results_v6").mkdir(exist_ok=True)
    (ROOT / "results_v6" / "action_mediation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

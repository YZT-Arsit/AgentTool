from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corpus_audit.ir_v1_freeze import verify_frozen_baseline

EXECUTABLE_KINDS = {"instructions", "llm", "termination", "tool", "handoff"}
IGNORED_BUCKET = "EXTRACTOR_FALSE_POSITIVE_OR_OUT_OF_SCOPE"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    verify_frozen_baseline(ROOT)
    output = ROOT / "WHOLE_WORKFLOW_EXECUTABLE_COVERAGE_V2.csv"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite versioned coverage: {output}")
    manifest = read(ROOT / "CORPUS_MANIFEST.csv")
    behaviors = read(ROOT / "CORPUS_BEHAVIOR_INSTANCES.csv")
    unsupported = read(ROOT / "IR_V1_UNSUPPORTED_INSTANCE_AUDIT.csv")
    by_file: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in behaviors:
        by_file[(row["framework"], row["relative_path"])].append(row)
    audit: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for row in unsupported:
        audit[(row["framework"], row["relative_path"], row["line"], row["behavior_kind"])].append(
            row["semantic_bucket"]
        )

    rows: list[dict[str, object]] = []
    for item in manifest:
        anchors = int(item["agent_constructors"]) + int(item["workflow_instances"])
        if anchors == 0:
            continue
        executable, unresolved, ignored = [], [], []
        for behavior in by_file[(item["framework"], item["relative_path"])]:
            key = (behavior["framework"], behavior["relative_path"], behavior["line"],
                   behavior["behavior_kind"])
            buckets = audit.get(key, [])
            if (behavior["disposition"] == "UNSUPPORTED" and buckets and
                    all(bucket == IGNORED_BUCKET for bucket in buckets)):
                ignored.append(f"{behavior['behavior_kind']}@{behavior['line']}")
            elif (behavior["behavior_kind"] in EXECUTABLE_KINDS and
                  behavior["disposition"] != "UNSUPPORTED"):
                executable.append(f"{behavior['behavior_kind']}@{behavior['line']}")
            else:
                unresolved.append(f"{behavior['behavior_kind']}@{behavior['line']}")
        if executable and not unresolved:
            status = "FULLY_EXECUTABLE"
        elif executable:
            status = "PARTIALLY_EXECUTABLE"
        else:
            status = "UNSUPPORTED"
        rows.append({
            "corpus_version": "IR-v1-frozen-membership",
            "framework": item["framework"], "pinned_commit": item["pinned_commit"],
            "relative_path": item["relative_path"], "workflow_unit": "SOURCE_FILE",
            "agent_constructors": item["agent_constructors"],
            "workflow_constructors": item["workflow_instances"],
            "status": status, "executable_behavior_instances": len(executable),
            "unresolved_behavior_instances": len(unresolved),
            "ignored_extractor_artifacts": len(ignored),
            "unresolved_families": ";".join(sorted({entry.split("@", 1)[0] for entry in unresolved})),
            "interpretation": "whole source-file workflow; all contained control behavior must close for FULL",
        })
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    counts = Counter(str(row["status"]) for row in rows)
    framework_counts = Counter((str(row["framework"]), str(row["status"])) for row in rows)
    summary = {
        "frozen_corpus_files": len(manifest), "workflow_source_file_units": len(rows),
        "not_workflow_files": len(manifest) - len(rows), "counts": counts,
        "fully_executable_fraction": counts["FULLY_EXECUTABLE"] / len(rows),
        "framework_counts": {f"{key[0]}::{key[1]}": value for key, value in sorted(framework_counts.items())},
        "definition": "source file is the conservative whole-workflow unit; FULL requires every non-artifact control behavior in the file to be executable-supported",
        "non_claim": "does not modify or replace the 3574/7386 behavior-instance baseline",
    }
    (ROOT / "WHOLE_WORKFLOW_EXECUTABLE_COVERAGE_V2.json").write_text(
        json.dumps(summary, indent=2, default=dict) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, default=dict))


if __name__ == "__main__":
    main()

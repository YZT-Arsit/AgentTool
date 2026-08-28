from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_control_virtualization.ir import AgentCapsule, ControlEvent, ControlRow, Opcode
from canonical_v3.runner import LocalProviderDefinition, run_canonical_gateway
from canonical_v3.workflows import WorkflowFixture
from privacy_kernel.control import OperationClass
from privacy_kernel.protocol import CanonicalProfile

FREEZE = ROOT / "LONG_HORIZON_STRUCTURAL_FREEZE.json"
DIGEST = ROOT / "LONG_HORIZON_STRUCTURAL_FREEZE_SHA256.txt"
OUTPUT = ROOT / "results_long_horizon_structural_v1"

PROVIDERS = (
    LocalProviderDefinition("FAST", 2, 4),
    LocalProviderDefinition("MEDIUM", 2, 4),
    LocalProviderDefinition("SLOW", 2, 4),
    LocalProviderDefinition("LOCAL_MODEL", 2, 4),
    LocalProviderDefinition("READ_ONLY_TOOL", 2, 4),
    LocalProviderDefinition("EFFECTFUL_TOOL", 2, 4, effectful=True),
)


def verify_freeze() -> dict[str, Any]:
    expected = DIGEST.read_text(encoding="utf-8").split()[0]
    if hashlib.sha256(FREEZE.read_bytes()).hexdigest() != expected:
        raise RuntimeError("long-horizon definition changed after freeze")
    return json.loads(FREEZE.read_text(encoding="utf-8"))


def capsule(agent: int, tool_handle: int, tool_name: str) -> AgentCapsule:
    return AgentCapsule(agent, agent + 1_000_000, 3, (
        ControlRow(Opcode.LLM, ControlEvent.START, 0, 1, label="model"),
        ControlRow(Opcode.TOOL, ControlEvent.MODEL_ACTION, 1, 2,
                   target_handle=tool_handle, label="private-tool"),
        ControlRow(Opcode.LLM, ControlEvent.TOOL_RESULT, 2, 3, label="model-resume"),
        ControlRow(Opcode.RETURN, ControlEvent.DONE, 3, 3, label="return"),
    ), "long-horizon-private-capsule")


def tool_fixture(agent: int, tool_handle: int, tool_name: str, provider: int = 7) -> WorkflowFixture:
    return WorkflowFixture(
        "PRIVATE_LONG_HORIZON", {agent: capsule(agent, tool_handle, tool_name)}, agent, 3, 0,
        {tool_handle: (provider, OperationClass.READ_ONLY_TOOL)}, {tool_handle: tool_name},
    )


def handoff_fixture(start: int, target: int) -> WorkflowFixture:
    first = AgentCapsule(start, start + 1_000_000, 3, (
        ControlRow(Opcode.HANDOFF, ControlEvent.START, 0, 0, target_handle=target, label="private-handoff"),
    ), "long-horizon-private-handoff")
    second = capsule(target, 8_000 + target, "READ_ONLY_TOOL")
    return WorkflowFixture(
        "PRIVATE_HANDOFF_LONG_HORIZON", {start: first, target: second}, start, 3, 0,
        {8_000 + target: (7, OperationClass.READ_ONLY_TOOL)},
        {8_000 + target: "READ_ONLY_TOOL"},
    )


def sequence(family: str, label: int) -> list[WorkflowFixture]:
    a = tool_fixture(100, 1000, "READ_ONLY_TOOL")
    b = tool_fixture(200, 2000, "READ_ONLY_TOOL")
    c = tool_fixture(300, 3000, "READ_ONLY_TOOL")
    local = tool_fixture(400, 4000, "LOCAL_TOOL", 1)
    remote = tool_fixture(500, 5000, "REMOTE_TOOL", 2)
    data, legal = a, b
    if family == "AGENT_IDENTITY": return [a if label == 0 else b] * 32
    if family == "HANDOFF_IDENTITY":
        return [handoff_fixture(600, 601) if label == 0 else handoff_fixture(600, 602) for _ in range(32)]
    if family == "TOOL_CLASS": return [local if label == 0 else remote] * 32
    if family == "FREQUENCY": return ([data] * 28 + [legal] * 4) if label == 0 else ([data, legal] * 16)
    if family == "RARE_TARGET":
        values = [data] * 32
        if label == 1: values[16] = legal
        return values
    if family == "TRANSITION_PATTERN": return [a, b] * 16 if label == 0 else [a, c] * 16
    if family == "REPEATED_TARGET": return [a, a] * 16 if label == 0 else [a, b] * 16
    if family == "CROSS_SESSION_LINKAGE": return [a, a] * 16 if label == 0 else [a, b] * 16
    raise KeyError(family)


def projection(rows: list[dict[str, Any]], profile_id: int) -> list[tuple[Any, ...]]:
    return [(row["direction"], row["session"], row["slot"], row["frame_bytes"],
             row["destination"], profile_id) for row in rows]


def run_case(profile: CanonicalProfile, family: str, label: int) -> dict[str, Any]:
    fixtures = sequence(family, label)
    kernels = []
    for ordinal, fixture in enumerate(fixtures):
        kernel = fixture.kernel()
        kernel._next_operation = (label + 1) * 100_000 + ordinal * 10  # private uniqueness only
        kernels.extend([kernel] * 4)
    case_dir = OUTPUT / family.lower() / f"class_{label}"
    result = run_canonical_gateway(ROOT, case_dir, profile, kernels[0], providers=PROVIDERS,
                                   kernel_sequence=tuple(kernels))
    rows = [json.loads(line) for line in
            (case_dir / "agentcloud_public_trace.jsonl").read_text(encoding="utf-8").splitlines()]
    public_projection = projection(rows, int(result["profile_id"]))
    (case_dir / "structural_size_projection.json").write_text(
        json.dumps(public_projection, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"family": family, "class": label, "summary": result,
            "projection": public_projection, "rows": rows}


def observation_features(case: dict[str, Any]) -> list[list[float]]:
    rows = case["rows"]
    features = []
    for observation in range(32):
        start, stop = observation * 4, (observation + 1) * 4
        selected = [row for row in rows if start <= int(row["session"]) < stop]
        features.append([
            len(selected),
            sum(row["direction"] == "REQUEST" for row in selected),
            sum(row["direction"] == "RESPONSE" for row in selected),
            sum(int(row["frame_bytes"]) for row in selected),
            len({row["destination"] for row in selected}),
            len({(row["session"] - start, row["slot"], row["direction"]) for row in selected}),
        ])
    return features


def classifier_checks(cases: list[dict[str, Any]], windows: list[int]) -> list[dict[str, Any]]:
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    results = []
    for window in windows:
        x, y, groups = [], [], []
        for family_index, family in enumerate(sorted({case["family"] for case in cases})):
            for case in [item for item in cases if item["family"] == family]:
                base = observation_features(case)
                for start in range(0, 32 - window + 1, window):
                    x.append(np.asarray(base[start:start + window]).sum(axis=0))
                    y.append(case["class"]); groups.append(family_index)
        x, y, groups = np.asarray(x), np.asarray(y), np.asarray(groups)
        train, test = groups < 6, groups >= 6
        for name, model in (
            ("LogisticRegression", LogisticRegression(max_iter=500, random_state=712)),
            ("RandomForestClassifier", RandomForestClassifier(n_estimators=200, random_state=712)),
        ):
            model.fit(x[train], y[train])
            score = model.predict_proba(x[test])[:, 1]
            results.append({"observation_count": window, "model": name,
                            "grouped_family_test_auc": roc_auc_score(y[test], score),
                            "feature_vectors_exactly_equal_by_label": bool(
                                np.array_equal(np.unique(x[y == 0], axis=0), np.unique(x[y == 1], axis=0))),
                            "permutation_baseline": 0.5,
                            "interpretation": "falsification check after exact equality"})
    return results


def main() -> None:
    definition = verify_freeze()
    if OUTPUT.exists() or (ROOT / "LONG_HORIZON_STRUCTURAL_RESULTS.csv").exists():
        raise FileExistsError("long-horizon frozen experiment already exists; refusing rerun")
    p = definition["public_profile"]
    profile = CanonicalProfile(p["name"], p["frame_bytes"], p["slots_per_session"],
                               p["total_sessions"], p["request_delta_ns"], p["response_delta_ns"],
                               p["mask_ns"], p["start_delay_ns"], p["inter_session_gap_ns"])
    cases = []
    summaries = []
    for item in definition["families"]:
        pair = [run_case(profile, item["family"], label) for label in (0, 1)]
        equal = pair[0]["projection"] == pair[1]["projection"]
        for case in pair:
            summaries.append({
                "family": case["family"], "class": case["class"],
                "exact_pair_projection_equal": equal,
                "public_events": len(case["projection"]),
                "frame_bytes_values": ";".join(map(str, sorted({row[3] for row in case["projection"]}))),
                "destination_values": ";".join(sorted({str(row[4]) for row in case["projection"]})),
                "real_heavy_operations": case["summary"]["real_heavy_operations"],
                "dummy_heavy_operations": case["summary"]["dummy_heavy_operations"],
                "effect_count": case["summary"]["effect_count"],
                "one_persistent_tunnel": case["summary"]["one_persistent_tunnel"],
            })
        cases.extend(pair)
    result_path = ROOT / "LONG_HORIZON_STRUCTURAL_RESULTS.csv"
    with result_path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader(); writer.writerows(summaries)
    checks = classifier_checks(cases, definition["aggregation_observation_counts"])
    with (ROOT / "LONG_HORIZON_CLASSIFIER_CHECKS.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(checks[0]))
        writer.writeheader(); writer.writerows(checks)
    final = {
        "freeze_id": definition["freeze_id"], "families": 8,
        "all_exact_structural_size_pairs_equal": all(row["exact_pair_projection_equal"] for row in summaries),
        "dummy_heavy_operations": sum(row["dummy_heavy_operations"] for row in summaries),
        "max_grouped_classifier_auc": max(row["grouped_family_test_auc"] for row in checks),
        "timing_privacy": "NOT_TESTED_BY_DESIGN",
    }
    (ROOT / "LONG_HORIZON_STRUCTURAL_SUMMARY.json").write_text(
        json.dumps(final, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(final, indent=2))


if __name__ == "__main__":
    main()

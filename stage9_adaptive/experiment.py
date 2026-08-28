from __future__ import annotations

import csv
import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev

from src.experiment import write_csv
from src.stage4 import binary_metrics

from .runtime import (
    FORBIDDEN_TRACE_FIELDS,
    SCENARIOS,
    TASKS,
    VARIANTS,
    AdaptiveNormalizer,
    MediationExecutor,
    assert_public_trace,
    derive_private_label,
    make_paired_episode,
)


def structural_signature(trace: list[dict[str, object]]) -> str:
    return ">".join(
        f"{event['round']}:{event['destination_service']}:{event['operation_class']}:{event['request_bytes']}:{event['response_bytes']}"
        for event in trace
    )


def structural_features(trace: list[dict[str, object]], include_paths: bool = False) -> list[str]:
    events = [f"{event['destination_service']}:{event['operation_class']}" for event in trace]
    rounds = [int(event["round"]) for event in trace]
    out = [f"event_count={len(trace)}", f"round_count={max(rounds, default=0)}"]
    out += [f"event_count:{key}={value}" for key, value in sorted(Counter(events).items())]
    out += [f"position:{index}:{token}" for index, token in enumerate(events)]
    out += [f"size:{index}:{event['request_bytes']}:{event['response_bytes']}" for index, event in enumerate(trace)]
    for n in (1, 2, 3):
        out += [f"ngram{n}:{'|'.join(events[index:index+n])}" for index in range(len(events) - n + 1)]
    if include_paths:
        out += [f"path:{index}:{event['physical_path']}" for index, event in enumerate(trace) if "physical_path" in event]
    return out


def split_indices(rows: list[dict[str, object]], split: str) -> tuple[list[int], list[int]]:
    if split == "grouped_entity":
        return (
            [index for index, row in enumerate(rows) if int(row["entity"]) % 4 != 3],
            [index for index, row in enumerate(rows) if int(row["entity"]) % 4 == 3],
        )
    if split == "cross_policy":
        return (
            [index for index, row in enumerate(rows) if int(row["policy_profile"]) < 2],
            [index for index, row in enumerate(rows) if int(row["policy_profile"]) >= 2],
        )
    if split == "cross_task":
        return (
            [index for index, row in enumerate(rows) if row["task"] == "SEND_MESSAGE"],
            [index for index, row in enumerate(rows) if row["task"] == "SHARE_DOCUMENT"],
        )
    raise ValueError(split)


def evaluate(rows: list[dict[str, object]], seed: int, scenario: str, variant: str) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    labels = [int(row["label"]) for row in rows]
    for level, include_paths in (("STRUCTURAL", False), ("FULL_ORAM", True)):
        features = [structural_features(row["trace"], include_paths) for row in rows]  # type: ignore[arg-type]
        for split in ("grouped_entity", "cross_policy", "cross_task"):
            train, test = split_indices(rows, split)
            if len(set(labels[index] for index in train)) < 2 or len(set(labels[index] for index in test)) < 2:
                continue
            accuracy, macro_f1, roc_auc = binary_metrics(features, labels, seed, train, test)
            permutation_metrics = []
            for repeat in range(24):
                shuffled = list(labels)
                random.Random(seed * 1009 + repeat * 7919 + 17).shuffle(shuffled)
                permutation_metrics.append(binary_metrics(features, shuffled, seed, train, test))
            for metric_index, (metric, value) in enumerate((('accuracy', accuracy), ('macro_f1', macro_f1), ('roc_auc', roc_auc))):
                output.append({
                    "seed": seed,
                    "scenario": scenario,
                    "variant": variant,
                    "feature_level": level,
                    "split": split,
                    "metric": metric,
                    "value": value,
                    "chance": 0.5,
                    "permutation": mean(item[metric_index] for item in permutation_metrics),
                })
    return output


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[float]] = defaultdict(list)
    permuted: dict[tuple[object, ...], list[float]] = defaultdict(list)
    keys = ("scenario", "variant", "feature_level", "split", "metric")
    for row in rows:
        key = tuple(row[name] for name in keys)
        grouped[key].append(float(row["value"]))
        permuted[key].append(float(row["permutation"]))
    return [
        {
            **dict(zip(keys, key)),
            "mean": mean(values),
            "std": pstdev(values),
            "chance": 0.5,
            "permutation_mean": mean(permuted[key]),
            "permutation_std": pstdev(permuted[key]),
        }
        for key, values in sorted(grouped.items())
    ]


def rank_auc(values: list[float], labels: list[int]) -> float:
    positive = [value for value, label in zip(values, labels) if label]
    negative = [value for value, label in zip(values, labels) if not label]
    return sum((a > b) + 0.5 * (a == b) for a in positive for b in negative) / (len(positive) * len(negative))


def svg_bars(path: Path, title: str, labels: list[str], values: list[float], ylabel: str, max_value: float) -> None:
    width, height, left, bottom, plot_height = 760, 440, 72, 366, 286
    colors = ("#4C78A8", "#F58518", "#54A24B", "#B9B9B9")
    spacing = 650 / len(labels)
    bars = []
    for index, (label, value) in enumerate(zip(labels, values)):
        x = left + index * spacing + 18
        bar_width = spacing - 36
        bar_height = plot_height * value / max_value
        y = bottom - bar_height
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{colors[index % len(colors)]}"/><text x="{x+bar_width/2:.1f}" y="{bottom+22}" text-anchor="middle">{label}</text><text x="{x+bar_width/2:.1f}" y="{y-7:.1f}" text-anchor="middle">{value:.3f}</text>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="white"/><style>text{{font:13px sans-serif}}.title{{font:bold 18px sans-serif}}</style><text x="380" y="28" text-anchor="middle" class="title">{title}</text><line x1="{left}" y1="80" x2="{left}" y2="{bottom}" stroke="black"/><line x1="{left}" y1="{bottom}" x2="730" y2="{bottom}" stroke="black"/><text x="18" y="220" transform="rotate(-90 18 220)" text-anchor="middle">{ylabel}</text>{"".join(bars)}</svg>'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def run_stage9(root: Path, pairs_per_cell: int = 40, seeds: tuple[int, ...] = (0, 1, 2), horizon: int = 5) -> dict[str, object]:
    root = Path(root)
    for directory in ("stage9_adaptive", "results_stage9", "figures_stage9"):
        (root / directory).mkdir(exist_ok=True)
    raw_path = root / "stage9_adaptive" / "raw_host_traces.jsonl"
    truth_rows: list[dict[str, object]] = []
    functional_rows: list[dict[str, object]] = []
    overhead_rows: list[dict[str, object]] = []
    symbolic_rows: list[dict[str, object]] = []
    timing_rows: list[dict[str, object]] = []
    evaluation_rows: list[dict[str, object]] = []
    datasets: dict[tuple[int, str, str], list[dict[str, object]]] = defaultdict(list)
    recorded_truth: set[tuple[int, int]] = set()
    started = time.perf_counter()

    with raw_path.open("w", encoding="utf-8") as raw:
        for seed in seeds:
            rng = random.Random(20260826 + seed)
            for scenario in SCENARIOS:
                for task in TASKS:
                    for pair_index in range(pairs_per_cell):
                        entity = rng.randrange(96)
                        policy_profile = rng.randrange(4)
                        captured: list[tuple[str, object, dict[str, object], list[dict[str, object]], list[dict[str, object]]]] = []
                        for branch in (0, 1):
                            episode_id = (((seed * len(SCENARIOS) + SCENARIOS.index(scenario)) * len(TASKS) + TASKS.index(task)) * pairs_per_cell + pair_index) * 2 + branch
                            episode = make_paired_episode(episode_id, scenario, task, branch, entity, policy_profile)
                            expected: dict[str, object] | None = None
                            for variant_index, variant in enumerate(VARIANTS):
                                executor = MediationExecutor(variant, horizon, seed * 10_000_000 + episode_id * 31 + variant_index)
                                result, trace, private_trace = executor.execute(episode)
                                if expected is None:
                                    expected = result
                                semantic_fields = ("authorized", "effect_count", "effect", "permission_exists", "provenance_exists", "requires_extra_verification", "sanitized_response", "final_outcome")
                                matches = all(result[field] == expected[field] for field in semantic_fields)
                                functional_rows.append({
                                    "seed": seed,
                                    "episode_id": episode_id,
                                    "scenario": scenario,
                                    "task": task,
                                    "branch": branch,
                                    "variant": variant,
                                    "matches_natural": matches,
                                    "authorization_equivalent": result["authorized"] == expected["authorized"],
                                    "effect_equivalent": result["effect"] == expected["effect"] and result["effect_count"] == expected["effect_count"],
                                    "dummy_external_effects": 0,
                                })
                                for event in trace:
                                    assert_public_trace([event])
                                    raw.write(json.dumps({"seed": seed, "episode_id": episode_id, "variant": variant, **event}, sort_keys=True, separators=(",", ":")) + "\n")
                                captured.append((variant, episode, result, trace, private_trace))
                        # The label is derived only after every variant trace was captured.
                        for variant, episode, result, trace, private_trace in captured:
                            label = derive_private_label(episode)  # type: ignore[arg-type]
                            row = {
                                "seed": seed,
                                "episode_id": episode.episode_id,  # type: ignore[attr-defined]
                                "scenario": scenario,
                                "task": task,
                                "entity": entity,
                                "policy_profile": policy_profile,
                                "label": label,
                                "trace": trace,
                                "result": result,
                            }
                            datasets[(seed, scenario, variant)].append(row)
                            truth_key = (seed, episode.episode_id)  # type: ignore[attr-defined]
                            if truth_key not in recorded_truth:
                                truth_rows.append({
                                    "seed": seed,
                                    "episode_id": episode.episode_id,  # type: ignore[attr-defined]
                                    "scenario": scenario,
                                    "task": task,
                                    "entity": entity,
                                    "policy_profile": policy_profile,
                                    "private_branch": label,
                                    "label_derived_after_capture": True,
                                })
                                recorded_truth.add(truth_key)

    for (seed, scenario, variant), rows in datasets.items():
        evaluation_rows += evaluate(rows, seed, scenario, variant)
        signatures = {
            branch: {structural_signature(row["trace"]) for row in rows if int(row["label"]) == branch}  # type: ignore[arg-type]
            for branch in (0, 1)
        }
        symbolic_rows.append({
            "seed": seed,
            "scenario": scenario,
            "variant": variant,
            "class0_unique_signatures": len(signatures[0]),
            "class1_unique_signatures": len(signatures[1]),
            "structural_sets_equal": signatures[0] == signatures[1],
            "structural_sets_disjoint": signatures[0].isdisjoint(signatures[1]),
            "signature_jaccard": len(signatures[0] & signatures[1]) / max(1, len(signatures[0] | signatures[1])),
        })
        for branch in (0, 1):
            selected = [row for row in rows if int(row["label"]) == branch]
            overhead_rows.append({
                "seed": seed,
                "scenario": scenario,
                "variant": variant,
                "private_branch": branch,
                "episodes": len(selected),
                "mean_private_operations": mean(int(row["result"]["real_private_ops"]) for row in selected),  # type: ignore[index]
                "mean_dummy_operations": mean(int(row["result"]["dummy_private_ops"]) for row in selected),  # type: ignore[index]
                "dummy_fraction": mean(int(row["result"]["dummy_private_ops"]) / max(1, int(row["result"]["real_private_ops"]) + int(row["result"]["dummy_private_ops"])) for row in selected),  # type: ignore[index]
                "mean_oram_accesses": mean(int(row["result"]["oram_accesses"]) for row in selected),  # type: ignore[index]
                "mean_wire_bytes": mean(int(row["result"]["wire_bytes"]) for row in selected),  # type: ignore[index]
                "mean_visible_rounds": mean(int(row["result"]["visible_rounds"]) for row in selected),  # type: ignore[index]
                "mean_latency_us": mean(float(row["result"]["latency_us"]) for row in selected),  # type: ignore[index]
                "mean_effect_latency_us": mean(float(row["result"]["effect_latency_us"]) for row in selected),  # type: ignore[index]
                "mean_trusted_state_bytes": mean(int(row["result"]["trusted_state_bytes"]) for row in selected),  # type: ignore[index]
            })
        timings = [float(row["result"]["latency_us"]) for row in rows]  # type: ignore[index]
        labels = [int(row["label"]) for row in rows]
        observed_auc = rank_auc(timings, labels)
        shuffled = []
        for repeat in range(32):
            permuted = list(labels)
            random.Random(seed * 1009 + repeat).shuffle(permuted)
            shuffled.append(rank_auc(timings, permuted))
        timing_rows.append({"seed": seed, "scenario": scenario, "variant": variant, "metric": "raw_latency_auc", "value": observed_auc, "chance": 0.5, "permutation": mean(shuffled), "scope": "OUT_OF_SCOPE"})

    horizon_rows: list[dict[str, object]] = []
    for tested_horizon in (3, 5, 8):
        for scenario in SCENARIOS:
            traces: dict[int, list[dict[str, object]]] = {}
            results: dict[int, dict[str, object]] = {}
            for branch in (0, 1):
                episode = make_paired_episode(900_000 + tested_horizon * 100 + SCENARIOS.index(scenario) * 2 + branch, scenario, "SEND_MESSAGE", branch, 7, 2)
                results[branch], traces[branch], _ = MediationExecutor("B2-ADAPTIVE-OBLIVIOUS", tested_horizon, 7000 + tested_horizon * 10 + branch).execute(episode)
            horizon_rows.append({
                "horizon": tested_horizon,
                "scenario": scenario,
                "required_horizon": AdaptiveNormalizer().compile(__import__('stage9_adaptive.ir', fromlist=['build_program']).build_program(scenario), tested_horizon).required_horizon,
                "overflow": bool(results[0]["overflow"]),
                "structural_equal": structural_signature(traces[0]) == structural_signature(traces[1]),
                "effect_count_class0": results[0]["effect_count"],
                "effect_count_class1": results[1]["effect_count"],
                "dummy_fraction_class0": int(results[0]["dummy_private_ops"]) / max(1, int(results[0]["dummy_private_ops"]) + int(results[0]["real_private_ops"])),
                "dummy_fraction_class1": int(results[1]["dummy_private_ops"]) / max(1, int(results[1]["dummy_private_ops"]) + int(results[1]["real_private_ops"])),
                "latency_us_class0": results[0]["latency_us"],
                "latency_us_class1": results[1]["latency_us"],
                "overflow_policy": "FAIL_CLOSED_FOR_ENTIRE_PUBLIC_PROGRAM_CLASS",
            })

    summary_rows = summarize(evaluation_rows)
    write_csv(root / "stage9_adaptive" / "private_ground_truth.csv", truth_rows)
    write_csv(root / "results_stage9" / "functional_equivalence.csv", functional_rows)
    write_csv(root / "results_stage9" / "symbolic_equality.csv", symbolic_rows)
    write_csv(root / "results_stage9" / "per_seed_inference.csv", evaluation_rows)
    write_csv(root / "results_stage9" / "inference_summary.csv", summary_rows)
    write_csv(root / "results_stage9" / "timing_augmented.csv", timing_rows)
    write_csv(root / "results_stage9" / "overhead.csv", overhead_rows)
    write_csv(root / "results_stage9" / "horizon_sensitivity.csv", horizon_rows)

    def auc_for(variant: str) -> float:
        values = [float(row["mean"]) for row in summary_rows if row["variant"] == variant and row["feature_level"] == "STRUCTURAL" and row["split"] == "grouped_entity" and row["metric"] == "roc_auc"]
        return mean(values)

    svg_bars(root / "figures_stage9" / "trajectory_structural_auc.svg", "Bounded trajectory leakage", ["NATURAL", "PER-ACTION", "ADAPTIVE"], [auc_for(variant) for variant in VARIANTS], "ROC-AUC", 1.0)
    svg_bars(root / "figures_stage9" / "horizon_dummy_fraction.svg", "Adaptive padding cost", ["H=3", "H=5", "H=8"], [mean(float(row["dummy_fraction_class0"]) + float(row["dummy_fraction_class1"]) for row in horizon_rows if int(row["horizon"]) == h) / 2 for h in (3, 5, 8)], "Dummy fraction", 1.0)
    svg_bars(root / "figures_stage9" / "round_overhead.svg", "Visible mediation rounds", ["NATURAL", "PER-ACTION", "ADAPTIVE"], [mean(float(row["mean_visible_rounds"]) for row in overhead_rows if row["variant"] == variant) for variant in VARIANTS], "Mean rounds", 6.0)
    return {
        "summary": summary_rows,
        "symbolic": symbolic_rows,
        "functional": functional_rows,
        "overhead": overhead_rows,
        "horizon": horizon_rows,
        "timing": timing_rows,
        "elapsed_s": time.perf_counter() - started,
    }

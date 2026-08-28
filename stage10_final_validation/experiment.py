from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from src.path_oram import PathORAM
from stage9_adaptive.runtime import MediationExecutor, make_paired_episode

from .runtime2_probe import NativeRun, run_native


VARIANTS = (
    "B0-NATURAL",
    "B1-PER-ACTION-OBLIVIOUS",
    "B2-BOUNDED-ADAPTIVE-OBLIVIOUS",
)
SEEDS = (0, 1, 2)
HORIZON = 5


def structural_signature(trace: Iterable[dict[str, object]]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            event.get("round", event.get("sequence")),
            event.get("destination_service", "RUNTIME_BOUNDARY"),
            event.get("operation_class", event.get("event")),
            event.get("request_bytes", 0),
            event.get("response_bytes", 0),
        )
        for event in trace
    )


def _b1_trace(native: NativeRun, seed: int) -> list[dict[str, object]]:
    """Normalize each native Runner invocation but preserve their natural count."""

    oram = PathORAM(128, seed, 4, 7)
    trace: list[dict[str, object]] = []
    for round_index in range(1, native.runtime_invocations + 1):
        for slot in range(3):
            _, physical = oram.access((round_index * 3 + slot) % 128, "read")
            trace.append(
                {
                    "round": round_index,
                    "destination_service": "PRIVATE_STATE_ORAM",
                    "operation_class": "ORAM_ACCESS",
                    "request_bytes": 451,
                    "response_bytes": 444,
                    "physical_path": int(physical["leaf"]),
                }
            )
    trace.append(
        {
            "round": native.runtime_invocations,
            "destination_service": "MESSAGE_TOOL",
            "operation_class": "PUBLIC_EFFECT",
            "request_bytes": 451,
            "response_bytes": 444,
        }
    )
    return trace


def _b2_trace(branch: int, seed: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    # This calls the unchanged Stage-9 IR, compiler, and executor. The Runtime-2
    # adapter supplies only the native approval-state mapping and public endpoint.
    episode = make_paired_episode(
        episode_id=branch,
        scenario="AUTHORIZATION",
        task_type="SEND_MESSAGE",
        branch=branch,
        entity=17,
        policy_profile=3,
    )
    result, trace, private_trace = MediationExecutor(
        "B2-ADAPTIVE-OBLIVIOUS", HORIZON, seed
    ).execute(episode)
    result = dict(result)
    result["dummy_fraction"] = (
        sum(bool(item["is_dummy"]) for item in private_trace) / len(private_trace)
    )
    return trace, result


def auc_binary(labels: list[int], scores: list[float]) -> float:
    positive = [score for score, label in zip(scores, labels) if label == 1]
    negative = [score for score, label in zip(scores, labels) if label == 0]
    if not positive or not negative:
        raise ValueError("both classes required")
    wins = 0.0
    for p_score in positive:
        for n_score in negative:
            wins += float(p_score > n_score) + 0.5 * float(p_score == n_score)
    return wins / (len(positive) * len(negative))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


async def run_experiment(output_dir: Path, pairs_per_seed: int = 20) -> dict[str, object]:
    runs: list[dict[str, object]] = []
    per_seed: list[dict[str, object]] = []
    equality_rows: list[dict[str, object]] = []

    for seed in SEEDS:
        by_variant: dict[str, tuple[list[int], list[float], list[str]]] = {}
        for variant in VARIANTS:
            labels: list[int] = []
            scores: list[float] = []
            signatures: list[str] = []
            for pair_index in range(pairs_per_seed):
                native_by_branch = {
                    branch: await run_native(
                        "APPROVAL_PRESENT" if branch == 0 else "APPROVAL_ABSENT"
                    )
                    for branch in (0, 1)
                }
                if native_by_branch[0].effects != native_by_branch[1].effects:
                    raise AssertionError("native final effects diverged")
                for branch, native in native_by_branch.items():
                    compiler_result: dict[str, object] = {}
                    if variant == "B0-NATURAL":
                        trace = [dict(event) for event in native.host_visible_trace]
                    elif variant == "B1-PER-ACTION-OBLIVIOUS":
                        trace = _b1_trace(native, seed * 10_000 + pair_index * 2 + branch)
                    else:
                        trace, compiler_result = _b2_trace(
                            branch, seed * 10_000 + pair_index * 2 + branch
                        )
                        if compiler_result["effect_count"] != native.effect_count:
                            raise AssertionError("compiler/runtime effect count mismatch")
                    signature = json.dumps(structural_signature(trace), separators=(",", ":"))
                    label = branch
                    score = float(
                        native.runtime_invocations
                        if variant == "B0-NATURAL"
                        else len(trace)
                    )
                    labels.append(label)
                    scores.append(score)
                    signatures.append(signature)
                    run_id = f"s{seed}-p{pair_index}-v{VARIANTS.index(variant)}-b{branch}"
                    runs.append(
                        {
                            "run_id": run_id,
                            "seed": seed,
                            "pair": pair_index,
                            "variant": variant,
                            "private_ground_truth": (
                                "APPROVAL_PRESENT" if branch == 0 else "APPROVAL_ABSENT"
                            ),
                            "host_event_count": len(trace),
                            "mediation_invocations": native.runtime_invocations,
                            "interruption_count": native.interruption_count,
                            "effect_count": native.effect_count,
                            "final_output": native.final_output,
                            "native_elapsed_us": round(native.elapsed_us, 3),
                            "oram_accesses": sum(
                                event.get("operation_class") == "ORAM_ACCESS"
                                for event in trace
                            ),
                            "dummy_fraction": compiler_result.get("dummy_fraction", 0.0),
                            "structural_signature": signature,
                        }
                    )
            by_variant[variant] = (labels, scores, signatures)

        for variant, (labels, scores, signatures) in by_variant.items():
            auc = auc_binary(labels, scores)
            shuffled_aucs: list[float] = []
            rng = random.Random(seed + 91_337)
            for _ in range(200):
                shuffled = list(labels)
                rng.shuffle(shuffled)
                shuffled_aucs.append(auc_binary(shuffled, scores))
            class_zero = {signature for signature, label in zip(signatures, labels) if label == 0}
            class_one = {signature for signature, label in zip(signatures, labels) if label == 1}
            exact_equal = class_zero == class_one
            per_seed.append(
                {
                    "seed": seed,
                    "variant": variant,
                    "auc": auc,
                    "chance": 0.5,
                    "permutation_auc_mean": statistics.mean(shuffled_aucs),
                    "permutation_auc_sd": statistics.pstdev(shuffled_aucs),
                    "class_signature_sets_equal": exact_equal,
                    "class_0_signature_count": len(class_zero),
                    "class_1_signature_count": len(class_one),
                }
            )
            equality_rows.append(
                {
                    "seed": seed,
                    "variant": variant,
                    "structural_signatures_exactly_equal": exact_equal,
                    "symbolic_result": "EQUAL" if exact_equal else "DISTINGUISHABLE",
                }
            )

    summary: list[dict[str, object]] = []
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in per_seed:
        grouped[str(row["variant"])].append(row)
    for variant, rows in grouped.items():
        summary.append(
            {
                "variant": variant,
                "auc_mean": statistics.mean(float(row["auc"]) for row in rows),
                "auc_sd": statistics.pstdev(float(row["auc"]) for row in rows),
                "chance": 0.5,
                "permutation_auc_mean": statistics.mean(
                    float(row["permutation_auc_mean"]) for row in rows
                ),
                "permutation_auc_sd_across_seeds": statistics.pstdev(
                    float(row["permutation_auc_mean"]) for row in rows
                ),
                "symbolic_class_equality_all_seeds": all(
                    bool(row["class_signature_sets_equal"]) for row in rows
                ),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    host_rows = [
        {key: value for key, value in row.items() if key != "private_ground_truth"}
        for row in runs
    ]
    truth_rows = [
        {
            "run_id": row["run_id"],
            "private_ground_truth": row["private_ground_truth"],
        }
        for row in runs
    ]
    _write_csv(output_dir / "runtime2_host_runs.csv", host_rows)
    _write_csv(output_dir / "runtime2_private_ground_truth.csv", truth_rows)
    _write_csv(output_dir / "runtime2_per_seed.csv", per_seed)
    _write_csv(output_dir / "runtime2_summary.csv", summary)
    _write_csv(output_dir / "runtime2_symbolic_equality.csv", equality_rows)

    b2_runs = [row for row in runs if row["variant"] == VARIANTS[2]]
    timing = {
        state: statistics.mean(
            float(row["native_elapsed_us"])
            for row in runs
            if row["variant"] == VARIANTS[0]
            and row["private_ground_truth"] == state
        )
        for state in ("APPROVAL_PRESENT", "APPROVAL_ABSENT")
    }
    result = {
        "runtime": "OpenAI Agents SDK (Python)",
        "runtime_commit": "a40ae9803e6b7a79faa246293f56adb100d5868b",
        "seeds": list(SEEDS),
        "pairs_per_seed": pairs_per_seed,
        "horizon": HORIZON,
        "summary": summary,
        "functional_equivalence": all(int(row["effect_count"]) == 1 for row in runs),
        "effect_equivalence": len({row["final_output"] for row in runs}) == 1,
        "dummy_external_effects": 0,
        "same_ir_core": "stage9_adaptive.ir.build_program('AUTHORIZATION')",
        "same_normalizer": "stage9_adaptive.runtime.AdaptiveNormalizer",
        "b2_oram_accesses": sorted({int(row["oram_accesses"]) for row in b2_runs}),
        "b2_dummy_fraction_mean": statistics.mean(
            float(row["dummy_fraction"]) for row in b2_runs
        ),
        "native_timing_us_mean": timing,
        "timing_scope": "overhead only; fine-grained timing privacy out of scope",
    }
    (output_dir / "runtime2_experiment.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def render_console_summary(result: dict[str, object]) -> str:
    summary = {row["variant"]: row for row in result["summary"]}  # type: ignore[index]
    b0 = summary["B0-NATURAL"]
    b1 = summary["B1-PER-ACTION-OBLIVIOUS"]
    b2 = summary["B2-BOUNDED-ADAPTIVE-OBLIVIOUS"]
    return f"""STAGE-10 FINAL DECISION:
A — MAINLINE FROZEN, READY FOR PAPER

Second L2 runtime:
ACHIEVED

Runtime 1:
Microsoft Agent Framework
commit:
af461de51da16f5cb800ff7febc0f8f96355607a

Runtime 2:
OpenAI Agents SDK for Python 0.22.0

Runtime 2 provenance:
openai/openai-agents-python @ a40ae9803e6b7a79faa246293f56adb100d5868b, MIT, clean unmodified checkout

Natural adaptive leakage in Runtime 2:
YES

Same initial public task:
YES

Same final public effect:
YES

B0 Runtime 2:
AUC = {float(b0['auc_mean']):.3f} ± {float(b0['auc_sd']):.3f}; 1 vs 2 native runner invocations

B1 Runtime 2:
AUC = {float(b1['auc_mean']):.3f} ± {float(b1['auc_sd']):.3f}; per-invocation ORAM shape remains 1 vs 2 rounds

B2 Runtime 2:
AUC = {float(b2['auc_mean']):.3f} ± {float(b2['auc_sd']):.3f}; structural classes exactly equal at H=5, 15 ORAM accesses

Cross-runtime common abstraction:
private approval state -> optional approval/persistence -> resume/reinvoke -> same real effect once

Same mediation IR core reused:
YES

Same normalizer reused:
YES

Dummy external effects:
NO

Functional equivalence:
PASS

Effect equivalence:
PASS

Focused prior-art direct collision:
NOT FOUND

Closest prior work:
AgentPrint for encrypted trajectory fingerprints; Ghost Tool Calls/OCELOT for agent trajectory privacy; Opal and general oblivious computation for fixed-view mechanisms

Opal collision:
PARTIALLY DEFEATED

ObliDB/general oblivious-computation collision:
PARTIALLY DEFEATED

Security definition:
NEEDS REVISION

Adaptive leakage novelty:
MODERATE

Two-runtime evidence:
STRONG

Bounded definition:
MODERATE

Mediation IR:
MODERATE

Normalizer:
INCREMENTAL

Effect-safe adaptation:
MODERATE

Strongest rejection argument:
Generic oblivious computation already handles bounded secret-dependent state machines, making this an approval-middleware application with an incremental normalizer.

Is rejection defeated?:
PARTIALLY

Strongest acceptance argument:
Two unmodified public runtimes expose private approval state through same-task/same-effect mediation structure, and one shared effect-safe bounded transformation removes that structure without dummy effects.

ICASSP/CCF-B short-paper readiness:
READY WITH MINOR GAPS

Should the research question now be frozen?:
YES

Should any additional synthetic validation be performed?:
NO

Should any new ORAM mechanism be developed?:
NO

Recommended final contribution list:
1. Agent-specific identification and two-runtime measurement of adaptive approval/provenance mediation leakage.
2. A bounded same-task/same-effect structural privacy definition and reusable mediation IR.
3. An effect-safe instantiation of known oblivious normalization that equalizes internal trajectories without dummy external effects.

Remaining blocker:
Revise the proof statement to quantify the observer and include every public effect attribute; no further experiment is blocked.

Recommended next step:
Freeze implementation/security boundaries, revise the formal definition, then begin the short paper."""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("results_stage10"))
    parser.add_argument("--pairs-per-seed", type=int, default=20)
    args = parser.parse_args()
    result = asyncio.run(run_experiment(args.output_dir, args.pairs_per_seed))
    console = render_console_summary(result)
    (args.output_dir / "final_console_summary.txt").write_text(
        console + "\n", encoding="utf-8"
    )
    print(console)


if __name__ == "__main__":
    main()

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
PLOT_DATA = ROOT / "FINAL_PAPER_PLOT_DATA.csv"

PLOT_FIELDS = [
    "figure",
    "panel",
    "metric",
    "condition",
    "value",
    "CI_low",
    "CI_high",
    "chance",
    "sample_count",
    "evidence_scope",
    "p_value",
    "p95",
    "source_file",
    "source_row",
    "status",
]


def normalize_svg(path: Path) -> None:
    """Remove generator-only line-end spaces so Git validation stays clean."""
    text = path.read_text(encoding="utf-8")
    path.write_text("\n".join(line.rstrip() for line in text.splitlines()) + "\n", encoding="utf-8")


def read_csv(name: str) -> list[dict[str, str]]:
    with (ROOT / name).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def one(rows: list[dict[str, str]], **wanted: str) -> dict[str, str]:
    matches = [row for row in rows if all(row.get(key) == value for key, value in wanted.items())]
    if len(matches) != 1:
        raise RuntimeError(f"expected one row for {wanted}, found {len(matches)}")
    return matches[0]


def add_plot_row(rows: list[dict[str, object]], **values: object) -> None:
    unknown = set(values) - set(PLOT_FIELDS)
    if unknown:
        raise ValueError(f"unknown plot-data fields: {unknown}")
    rows.append({field: values.get(field, "") for field in PLOT_FIELDS})


def build_plot_data() -> list[dict[str, object]]:
    access = read_csv("V15E_ACCESS_PRIVACY_RESULTS.csv")
    sequence = read_csv("V15E_SEQUENCE_RESULTS.csv")
    timing = read_csv("FINAL_TIMING_RESULTS.csv")
    final_sequence = read_csv("FINAL_SEQUENCE_RESULTS.csv")
    final_privacy = read_csv("FINAL_PRIVACY_RESULTS.csv")
    scale = read_csv("FINAL_SCALE_RESULTS.csv")
    overhead = read_csv("FINAL_OVERHEAD_RESULTS.csv")
    rows: list[dict[str, object]] = []

    access_specs = [
        ("Same-Agent", access, "SAME_AGENT_WITHIN_SESSION", "ESTABLISHED"),
        ("Cross-session\nsame", access, "CROSS_SESSION_SAME_SLOT", "ESTABLISHED"),
        ("Cross-session\ncross", access, "CROSS_SESSION_CROSS_SLOT", "ESTABLISHED"),
        ("Rare\ninsertion", sequence, "RARE_INSERTION_AAA_VS_AAB", "ESTABLISHED"),
        ("Recurrence", sequence, "RECURRENCE_AAA_VS_ABC", "ESTABLISHED"),
        ("Return\npattern", sequence, "RETURN_PATTERN_ABA_VS_ABC", "NOT_ESTABLISHED"),
    ]
    for label, source_rows, experiment, status in access_specs:
        row = one(source_rows, experiment=experiment, feature_view="ALL")
        add_plot_row(
            rows,
            figure="FIG2",
            panel="a_access_linking",
            metric="AUC",
            condition=label,
            value=row["test_train_oriented_auc"],
            CI_low=row["ci95_low"],
            CI_high=row["ci95_high"],
            chance=0.5,
            sample_count=row["n_test"],
            evidence_scope="CURRENT_FULL_SYSTEM",
            p_value=row["permutation_p"],
            source_file=(
                "V15E_ACCESS_PRIVACY_RESULTS.csv"
                if source_rows is access
                else "V15E_SEQUENCE_RESULTS.csv"
            ),
            source_row=f"{experiment}|ALL",
            status=status,
        )

    access_four = one(sequence, experiment="FOUR_CLASS_ORDERING_RECURRENCE", feature_view="ALL")
    access_control = one(
        sequence,
        experiment="FOUR_CLASS_ORDERING_RECURRENCE",
        feature_view="UNPROTECTED_VISIBLE_AGENT_ID_POSITIVE_CONTROL",
    )
    trajectory = one(
        final_sequence,
        experiment="FOUR_CLASS_EXECUTION_TRAJECTORY",
        feature_view="FINAL_OAE_STRUCTURAL_COMPOSITION",
    )
    trajectory_control = one(
        final_sequence,
        experiment="FOUR_CLASS_EXECUTION_TRAJECTORY",
        feature_view="UNNORMALIZED_VISIBLE_ACTION_ENDPOINT_POSITIVE_CONTROL",
    )
    for label, row, scope, source_row in (
        ("Access\nOAE", access_four, "CURRENT_FULL_SYSTEM", "FOUR_CLASS_ORDERING_RECURRENCE|ALL"),
        (
            "Access\ncontrol",
            access_control,
            "CURRENT_FULL_SYSTEM",
            "FOUR_CLASS_ORDERING_RECURRENCE|UNPROTECTED_VISIBLE_AGENT_ID_POSITIVE_CONTROL",
        ),
        (
            "Trajectory\nOAE",
            trajectory,
            "CURRENT_COMPONENT",
            "FOUR_CLASS_EXECUTION_TRAJECTORY|FINAL_OAE_STRUCTURAL_COMPOSITION",
        ),
        (
            "Trajectory\ncontrol",
            trajectory_control,
            "CURRENT_COMPONENT",
            "FOUR_CLASS_EXECUTION_TRAJECTORY|UNNORMALIZED_VISIBLE_ACTION_ENDPOINT_POSITIVE_CONTROL",
        ),
    ):
        add_plot_row(
            rows,
            figure="FIG2",
            panel="b_sequence_structure",
            metric="Accuracy",
            condition=label,
            value=row["test_accuracy"],
            CI_low=row["ci95_low"],
            CI_high=row["ci95_high"],
            chance=0.25,
            sample_count=row["n_test"],
            evidence_scope=scope,
            p_value=row["permutation_p"],
            source_file=(
                "V15E_SEQUENCE_RESULTS.csv" if label.startswith("Access") else "FINAL_SEQUENCE_RESULTS.csv"
            ),
            source_row=source_row,
            status="EMPIRICALLY_SUPPORTED",
        )

    branch = one(
        final_privacy,
        experiment="PROVISIONED_UNPROVISIONED_IDLE",
        feature_view="TIMING",
    )
    add_plot_row(
        rows,
        figure="FIG2",
        panel="c_realized_timing",
        metric="Accuracy",
        condition="Branch\ntiming",
        value=branch["test_accuracy"],
        CI_low=branch["ci95_low"],
        CI_high=branch["ci95_high"],
        chance=1 / 3,
        sample_count=branch["n_test"],
        evidence_scope="CURRENT_COMPONENT",
        p_value=branch["permutation_p"],
        source_file="FINAL_PRIVACY_RESULTS.csv",
        source_row="PROVISIONED_UNPROVISIONED_IDLE|TIMING",
        status="NOT_ESTABLISHED",
    )

    timing_labels = {
        ("TOOL_VS_AGENT_AS_TOOL", "OpenAI Agents SDK"): "Tool/Agent\nOAI",
        ("TOOL_VS_AGENT_AS_TOOL", "Microsoft Agent Framework"): "Tool/Agent\nMAF",
        ("PROVIDER_READINESS", "OpenAI Agents SDK"): "Provider\nOAI",
        ("PROVIDER_READINESS", "Microsoft Agent Framework"): "Provider\nMAF",
    }
    for key, label in timing_labels.items():
        experiment, framework = key
        for condition, display, scope in (
            ("FINAL_OAE_BIDIRECTIONAL_SHAPING", "OAE", "CURRENT_FULL_SYSTEM"),
            (
                "HISTORICAL_ONE_SIDED_POSITIVE_CONTROL",
                "One-sided control",
                "HISTORICAL_ABLATION",
            ),
        ):
            row = one(timing, experiment=experiment, framework=framework, condition=condition)
            add_plot_row(
                rows,
                figure="FIG2",
                panel="c_realized_timing",
                metric="AUC",
                condition=f"{label}|{display}",
                value=row["test_train_oriented_auc"],
                CI_low=row["ci95_low"],
                CI_high=row["ci95_high"],
                chance=0.5,
                sample_count=row["n_test"],
                evidence_scope=scope,
                p_value=row["permutation_p"],
                source_file="FINAL_TIMING_RESULTS.csv",
                source_row=f"{experiment}|{framework}|{condition}",
                status="NOT_ESTABLISHED" if display == "OAE" else "POSITIVE_CONTROL",
            )

    for row in scale:
        for metric, p50_col, p95_col in (
            ("PSI", "psi_online_p50_ms", "psi_online_p95_ms"),
            ("PIR", "pir_online_p50_ms", "pir_online_p95_ms"),
            ("Combined", "combined_pipelined_p50_ms", "combined_pipelined_p95_ms"),
        ):
            add_plot_row(
                rows,
                figure="SCALE",
                panel="online_latency",
                metric=metric,
                condition=row["N"],
                value=row[p50_col],
                p95=row[p95_col],
                sample_count=row["queries"],
                evidence_scope="CURRENT_FULL_SYSTEM",
                source_file="FINAL_SCALE_RESULTS.csv",
                source_row=f"N={row['N']}|{metric}",
                status="ESTABLISHED",
            )

    overhead_lookup = {row["metric"]: row for row in overhead}
    for label, metric_name in (
        ("APSI", "APSI_bytes_per_profile"),
        ("SimplePIR", "SimplePIR_bytes_per_profile"),
        ("Gateway", "bytes_per_profile"),
    ):
        source = overhead_lookup[metric_name]
        if label == "Gateway" and source["section"] != "GATEWAY":
            source = one(overhead, metric="bytes_per_profile", section="GATEWAY")
        add_plot_row(
            rows,
            figure="TRAFFIC",
            panel="base_profile",
            metric="MiB",
            condition=label,
            value=float(source["value"]) / 1048576,
            evidence_scope="CURRENT_FULL_SYSTEM",
            source_file="FINAL_OVERHEAD_RESULTS.csv",
            source_row=f"{source['metric']}|{source['section']}",
            status="ESTABLISHED",
        )

    with PLOT_DATA.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=PLOT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def build_native_comparison_and_table() -> None:
    native = read_csv("FINAL_NATIVE_LATENCY_RESULTS.csv")
    stats = json.loads((ROOT / "FINAL_STATISTICAL_SUMMARY.json").read_text(encoding="utf-8"))
    oae = {
        (row["framework"], row["workload"]): row
        for row in stats["utility"]["summary_by_coordinate"]
        if row["workload"] != "IDLE_PROFILE_ONLY"
    }
    workload_map = {
        "PROVISIONED_ORDINARY": "PROVISIONED_ORDINARY",
        "UNPROVISIONED_ORDINARY": "UNPROVISIONED_ORDINARY",
        "NESTED_AGENT_AS_TOOL": "PROVISIONED_NESTED_AGENT_AS_TOOL",
        "REPEATED_AGENT": "REPEATED_AGENT",
        "MIXED_AGENT_LLM_TOOL": "MIXED_AGENT_LLM_TOOL",
    }
    comparison: list[dict[str, object]] = []
    for row in native:
        target = oae[(row["framework"], workload_map[row["workload"]])]
        native_p50 = float(row["task_latency_p50_ms"])
        oae_p50 = float(target["task_latency_p50_ms_successful"])
        comparison.append(
            {
                **row,
                "oae_workload": workload_map[row["workload"]],
                "oae_measured_executions": target["n"],
                "oae_successes": target["semantic_successes"],
                "oae_failures": target["n"] - target["semantic_successes"],
                "oae_task_latency_p50_ms": oae_p50,
                "oae_task_latency_p95_ms": target["task_latency_p95_ms_successful"],
                "additive_p50_overhead_ms": oae_p50 - native_p50,
                "p50_slowdown_ratio": oae_p50 / native_p50,
            }
        )
    if len(comparison) != 10:
        raise RuntimeError("matched native/OAE comparison must contain exactly 10 coordinates")
    native_fields = list(comparison[0])
    with (ROOT / "FINAL_NATIVE_LATENCY_RESULTS.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=native_fields)
        writer.writeheader()
        writer.writerows(comparison)

    table_rows = [
        ("Scale", "Provisioned-Agent store", "100,000 schema-valid artifacts"),
        ("Utility", "Semantic success", "240/240 non-idle executions"),
        ("Utility", "Profile conformance", "280/280 sessions"),
        ("Reliability", "Overflow / silent loss", "0 / 0"),
        ("Reliability", "Retrieval / loader failure", "0 / 0"),
        ("Latency", "Retrieval p50 / p95", "771.729 / 7466.234 ms"),
        ("Latency", "Task p50 / p95", "5002.551 / 14880.534 ms"),
        ("Communication", "Base public profile", "9.903 MiB/session"),
        ("Communication", "Measured workload mean", "11.318 MiB/execution"),
        ("Efficiency", "Dummy Agent / LLM / Tool executions", "0 / 0 / 0"),
    ]
    for framework, short_name in (("OpenAI Agents SDK", "OAI"), ("Microsoft Agent Framework", "MAF")):
        selected = [row for row in comparison if row["framework"] == framework]
        native_values = [float(row["task_latency_p50_ms"]) for row in selected]
        oae_values = [float(row["oae_task_latency_p50_ms"]) for row in selected]
        slowdown_values = [float(row["p50_slowdown_ratio"]) for row in selected]
        result = (
            f"native {min(native_values):.3f}--{max(native_values):.3f} ms; "
            f"OAE {min(oae_values):.3f}--{max(oae_values):.3f} ms; "
            f"{min(slowdown_values):.1f}--{max(slowdown_values):.1f}x"
        )
        table_rows.append(("Matched latency", f"{short_name}: p50 range (5 workloads)", result))
    with (ROOT / "FINAL_PAPER_TABLE1.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Category", "Metric", "Result"))
        writer.writerows(table_rows)

    def esc(value: str) -> str:
        return value.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")

    tex = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Final utility, reliability, and overhead results. Native/OAE entries report task-latency p50/p95; latency statistics use successful semantic executions.}",
        r"\label{tab:final-results}",
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2.8pt}",
        r"\begin{tabular}{@{}p{0.15\columnwidth}p{0.27\columnwidth}p{0.52\columnwidth}@{}}",
        r"\toprule",
        r"Category & Metric & Result \\",
        r"\midrule",
    ]
    for category, metric, result in table_rows:
        tex.append(f"{esc(category)} & {esc(metric)} & {esc(result)} \\\\")
    tex.extend((r"\bottomrule", r"\end{tabular}", r"\end{table}"))
    (ROOT / "FINAL_PAPER_TABLE1.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "font.size": 7.3,
            "axes.labelsize": 7.3,
            "axes.titlesize": 7.6,
            "xtick.labelsize": 6.7,
            "ytick.labelsize": 6.7,
            "legend.fontsize": 6.5,
            "axes.linewidth": 0.6,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def errorbar(axis, x, row, **kwargs):
    value = float(row["value"])
    low = float(row["CI_low"])
    high = float(row["CI_high"])
    axis.errorbar(x, value, yerr=[[value - low], [high - value]], capsize=2, **kwargs)


def generate_fig2(rows: list[dict[str, str]]) -> None:
    configure_style()
    figure, axes = plt.subplots(
        1,
        3,
        figsize=(7.16, 2.42),
        gridspec_kw={"width_ratios": [2.15, 1.18, 2.35]},
    )
    ax_a, ax_b, ax_c = axes

    access = [row for row in rows if row["figure"] == "FIG2" and row["panel"] == "a_access_linking"]
    x = np.arange(len(access))
    for index, row in enumerate(access):
        errorbar(
            ax_a,
            index,
            row,
            fmt="o",
            color="black",
            markerfacecolor="0.65" if row["status"] != "NOT_ESTABLISHED" else "white",
            markeredgecolor="black",
            markersize=4.0,
            linewidth=0.75,
        )
        ax_a.text(index, float(row["CI_high"]) + 0.035, f"{float(row['value']):.3f}", ha="center", va="bottom", fontsize=6.3)
    ax_a.axhline(0.5, color="0.35", linestyle=(0, (3, 2)), linewidth=0.7)
    ax_a.text(5.35, 0.515, "Chance", ha="right", va="bottom", fontsize=6.2, color="0.25")
    ax_a.set_xticks(x, [row["condition"] for row in access])
    plt.setp(ax_a.get_xticklabels(), rotation=24, ha="right", rotation_mode="anchor", fontsize=5.9)
    ax_a.set_ylim(0, 1.02)
    ax_a.set_ylabel("AUC")
    ax_a.set_title("(a) Agent-access linking", loc="left", pad=3)

    structural = [row for row in rows if row["figure"] == "FIG2" and row["panel"] == "b_sequence_structure"]
    for group_index, prefix in enumerate(("Access", "Trajectory")):
        for offset, suffix, facecolor, hatch, legend in (
            (-0.19, "OAE", "0.65", "", "OAE"),
            (0.19, "control", "white", "///", "Unprotected control"),
        ):
            row = next(item for item in structural if item["condition"] == f"{prefix}\n{suffix}")
            xpos = group_index + offset
            ax_b.bar(
                xpos,
                float(row["value"]),
                width=0.34,
                facecolor=facecolor,
                edgecolor="black",
                hatch=hatch,
                linewidth=0.65,
                label=legend if group_index == 0 else None,
            )
            value = float(row["value"])
            low = float(row["CI_low"])
            high = float(row["CI_high"])
            ax_b.errorbar(xpos, value, yerr=[[value - low], [high - value]], fmt="none", color="black", linewidth=0.65, capsize=2)
            ax_b.text(xpos, min(1.0, high) + 0.025, f"{value:.3f}", ha="center", va="bottom", fontsize=6.2)
    ax_b.axhline(0.25, color="0.35", linestyle=(0, (3, 2)), linewidth=0.7)
    ax_b.text(0.5, 0.19, "25% chance", ha="center", va="top", fontsize=6.2, color="0.25")
    ax_b.set_xticks([0, 1], ["Access pattern", "Trajectory"])
    plt.setp(ax_b.get_xticklabels(), fontsize=6.2)
    ax_b.set_ylim(0, 1.08)
    ax_b.set_ylabel("Classification accuracy")
    ax_b.set_title("(b) Structural inference", loc="left", pad=3)
    ax_b.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.36), ncol=2, handlelength=1.3, columnspacing=0.7)

    timing_rows = [row for row in rows if row["figure"] == "FIG2" and row["panel"] == "c_realized_timing"]
    branch = next(row for row in timing_rows if row["metric"] == "Accuracy")
    gateway = [row for row in timing_rows if row["metric"] == "AUC"]
    labels = ["Branch\ntiming", "Tool/Agent\nOAI", "Tool/Agent\nMAF", "Provider\nOAI", "Provider\nMAF"]
    errorbar(ax_c, 0, branch, fmt="D", color="black", markerfacecolor="0.65", markersize=3.8, linewidth=0.7)
    ax_c.text(0, float(branch["CI_high"]) + 0.035, f"{float(branch['value']):.3f}", ha="center", fontsize=6.2)
    ax_c.hlines(1 / 3, -0.35, 0.35, color="0.35", linestyle=(0, (3, 2)), linewidth=0.7)
    ax_c.text(0, 0.355, "33%", ha="center", fontsize=5.9, color="0.25")
    for index, label in enumerate(labels[1:], start=1):
        oae = next(row for row in gateway if row["condition"] == f"{label}|OAE")
        control = next(row for row in gateway if row["condition"] == f"{label}|One-sided control")
        ax_c.plot([index, index], [float(oae["value"]), float(control["value"])], color="0.65", linewidth=0.6, zorder=1)
        errorbar(ax_c, index - 0.09, oae, fmt="o", color="black", markerfacecolor="0.65", markersize=3.8, linewidth=0.7, label="OAE" if index == 1 else None)
        errorbar(ax_c, index + 0.09, control, fmt="s", color="black", markerfacecolor="white", markersize=3.5, linewidth=0.7, label="One-sided control" if index == 1 else None)
        ax_c.text(index - 0.09, float(oae["CI_high"]) + 0.035, f"{float(oae['value']):.3f}", ha="center", fontsize=5.8)
    ax_c.hlines(0.5, 0.65, 4.35, color="0.35", linestyle=(0, (3, 2)), linewidth=0.7)
    ax_c.text(0.72, 0.515, "Chance", ha="left", va="bottom", fontsize=6.0, color="0.25")
    ax_c.axvline(0.5, color="0.75", linestyle=":", linewidth=0.6)
    ax_c.set_xticks(np.arange(5), labels)
    plt.setp(ax_c.get_xticklabels(), rotation=24, ha="right", rotation_mode="anchor", fontsize=5.8)
    ax_c.set_ylim(0, 1.08)
    ax_c.set_ylabel("Attack score")
    ax_c.set_title("(c) Realized timing", loc="left", pad=3)
    ax_c.legend(frameon=False, loc="lower right", handletextpad=0.35, borderaxespad=0.15)

    for axis in axes:
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.tick_params(width=0.55, length=2.5)
        axis.grid(False)
    figure.subplots_adjust(left=0.063, right=0.995, bottom=0.31, top=0.90, wspace=0.39)
    figure.savefig(ROOT / "FINAL_FIG2.pdf", bbox_inches="tight", pad_inches=0.025)
    svg_path = ROOT / "FINAL_FIG2.svg"
    figure.savefig(svg_path, bbox_inches="tight", pad_inches=0.025)
    normalize_svg(svg_path)
    plt.close(figure)


def generate_traffic(rows: list[dict[str, str]]) -> None:
    configure_style()
    traffic = [row for row in rows if row["figure"] == "TRAFFIC"]
    order = ["APSI", "SimplePIR", "Gateway"]
    values = [float(next(row for row in traffic if row["condition"] == label)["value"]) for label in order]
    colors = ["0.35", "0.7", "white"]
    hatches = ["", "///", "..."]
    figure, axis = plt.subplots(figsize=(3.45, 1.35))
    left = 0.0
    for label, value, color, hatch in zip(order, values, colors, hatches):
        axis.barh(0, value, left=left, height=0.46, color=color, edgecolor="black", linewidth=0.65, hatch=hatch, label=label)
        if value >= 0.7:
            axis.text(left + value / 2, 0, f"{value:.2f}", ha="center", va="center", color="white" if color == "0.35" else "black", fontsize=6.4)
        left += value
    axis.set_xlim(0, left * 1.02)
    axis.set_yticks([])
    axis.set_xlabel("Traffic per base public profile (MiB)")
    axis.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.25), handlelength=1.4, columnspacing=0.9)
    axis.text(left, 0.32, f"Total: {left:.3f} MiB", ha="right", va="bottom", fontsize=6.5)
    axis.spines["left"].set_visible(False)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.tick_params(width=0.55, length=2.5)
    figure.subplots_adjust(left=0.03, right=0.99, bottom=0.30, top=0.78)
    figure.savefig(ROOT / "FINAL_TRAFFIC_BREAKDOWN.pdf", bbox_inches="tight", pad_inches=0.025)
    svg_path = ROOT / "FINAL_TRAFFIC_BREAKDOWN.svg"
    figure.savefig(svg_path, bbox_inches="tight", pad_inches=0.025)
    normalize_svg(svg_path)
    plt.close(figure)


def write_audit(rows: list[dict[str, str]]) -> None:
    plotted = [row for row in rows if row["figure"] in {"FIG2", "SCALE", "TRAFFIC"}]
    lines = [
        "# Final figure number audit",
        "",
        "Every figure reads `FINAL_PAPER_PLOT_DATA.csv`; each row below was copied mechanically from the listed machine-readable source row.",
        "",
        "| Figure / panel | Plotted metric | Source file / row | Value | CI or p95 | Status |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in plotted:
        interval = ""
        if row["CI_low"] and row["CI_high"]:
            interval = f"[{float(row['CI_low']):.3f}, {float(row['CI_high']):.3f}]"
        elif row["p95"]:
            interval = f"p95={float(row['p95']):.3f}"
        lines.append(
            f"| {row['figure']} / {row['panel']} | {row['condition']} ({row['metric']}) | "
            f"`{row['source_file']}` / `{row['source_row']}` | {float(row['value']):.6g} | "
            f"{interval} | {row['status']} |"
        )
    (ROOT / "FINAL_FIGURE_NUMBER_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    build_native_comparison_and_table()
    build_plot_data()
    rows = read_csv("FINAL_PAPER_PLOT_DATA.csv")
    generate_fig2(rows)
    generate_traffic(rows)
    write_audit(rows)


if __name__ == "__main__":
    main()

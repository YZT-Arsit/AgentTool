from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent


def normalize_svg(path: Path) -> None:
    """Remove generator-only line-end spaces so Git validation stays clean."""
    text = path.read_text(encoding="utf-8")
    path.write_text("\n".join(line.rstrip() for line in text.splitlines()) + "\n", encoding="utf-8")


def main() -> None:
    with (ROOT / "FINAL_PAPER_PLOT_DATA.csv").open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream) if row["figure"] == "SCALE"]
    if len(rows) != 12:
        raise RuntimeError(f"expected 12 scale rows, found {len(rows)}")

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "font.size": 7.5,
            "axes.labelsize": 7.5,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 6.8,
            "axes.linewidth": 0.6,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
    styles = {
        "PSI": ("o", "-", "0.15"),
        "PIR": ("s", "--", "0.45"),
        "Combined": ("^", "-.", "0.7"),
    }
    figure, axis = plt.subplots(figsize=(3.45, 2.0))
    for metric in ("PSI", "PIR", "Combined"):
        selected = sorted((row for row in rows if row["metric"] == metric), key=lambda row: int(row["condition"]))
        x = [int(row["condition"]) for row in selected]
        p50 = [float(row["value"]) for row in selected]
        p95 = [float(row["p95"]) for row in selected]
        marker, line, color = styles[metric]
        axis.plot(x, p50, marker=marker, linestyle=line, color=color, linewidth=0.85, markersize=3.6, label=metric)
        axis.vlines(x, p50, p95, color=color, linewidth=0.65)
        axis.scatter(x, p95, marker="_", color=color, s=13, linewidths=0.75)
    axis.set_xscale("log")
    axis.set_xticks([1000, 10000, 50000, 100000], ["1K", "10K", "50K", "100K"])
    axis.set_xlabel("Provisioned-Agent records")
    axis.set_ylabel("Online latency (ms)")
    axis.set_ylim(0, 70)
    axis.legend(frameon=False, ncol=3, loc="upper left", columnspacing=0.8, handlelength=1.8)
    axis.text(0.99, 0.03, "points: p50; caps: p95", transform=axis.transAxes, ha="right", va="bottom", fontsize=6.2, color="0.3")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.tick_params(width=0.55, length=2.5)
    axis.grid(False)
    figure.subplots_adjust(left=0.16, right=0.99, bottom=0.22, top=0.93)
    figure.savefig(ROOT / "FINAL_SCALE_FIG.pdf", bbox_inches="tight", pad_inches=0.025)
    svg_path = ROOT / "FINAL_SCALE_FIG.svg"
    figure.savefig(svg_path, bbox_inches="tight", pad_inches=0.025)
    normalize_svg(svg_path)
    plt.close(figure)


if __name__ == "__main__":
    main()

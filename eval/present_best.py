"""Presentation figures for the best GISD test-set run alone (no baseline comparison).

Reads the run's `metrics.json` and `cases.csv` and writes 16:9 PNGs in OneSTOP brand style:

    uv run --project eval eval/present_best.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

from eicat_eval import charts, style
from eicat_eval.eicat import CATEGORY_NAMES, MECHANISM_LABELS, category_label
from eicat_eval.paths import EVAL
from eicat_eval.runs import class_accuracy, read_cases, read_metrics
from eicat_eval.style import DARK, GREEN, GRID, INK, LIGHT, MUTED, SURFACE

RUN, MODEL, PROMPT = "t60_v2_haiku", "Haiku 5.5", "Improved"  # best F2, category and max-category accuracy
NAME = f"{MODEL}, {PROMPT.lower()} prompt"


# ── 1. headline numbers ───────────────────────────────────────────────────────


def fig_headline(m: dict, cases: pd.DataFrame, out: Path) -> None:
    within_one = (cases["max_category_distance"] <= 1).sum()
    tiles = [
        (f"{m['detection']['micro']['recall']:.0%}", "of GISD impacts\nfound", "detection recall"),
        (f"{m['detection']['micro']['f2']:.2f}", "F2 for impact\ndetection", "recall-weighted"),
        (f"{m['labels']['mechanism']['matched']['micro']['recall']:.0%}", "mechanism labels\ncorrect",
         "on impacts\nmatched to GISD"),
        (f"{m['labels']['category']['matched']['micro']['recall']:.0%}", "category labels\ncorrect",
         "on impacts\nmatched to GISD"),
        (f"{within_one / len(cases):.0%}", "of papers within\none category",
         f"most severe category\n{within_one} of {len(cases)} papers"),
    ]
    fig, ax = style.slide(f"EICAT-AI on unseen papers: {NAME}",
                          f"{m['n_cases_scored']} papers, {m['n_gold_impacts']} GISD impacts.")
    ax.set_axis_off()
    width = 1 / len(tiles)
    for i, (value, label, detail) in enumerate(tiles):
        x = i * width + 0.012
        ax.add_patch(FancyBboxPatch((x, 0.12), width - 0.024, 0.72, transform=ax.transAxes,
                                    boxstyle="round,pad=0,rounding_size=0.02", facecolor=LIGHT, edgecolor="none"))
        cx = x + (width - 0.024) / 2
        ax.text(cx, 0.6, value, transform=ax.transAxes, ha="center", va="center", fontsize=54,
                fontfamily=style.HEADING, fontweight="bold", color=DARK)
        ax.text(cx, 0.38, label, transform=ax.transAxes, ha="center", va="center", fontsize=14.5, color=INK, linespacing=1.3)
        ax.text(cx, 0.2, detail, transform=ax.transAxes, ha="center", va="center", fontsize=10.5, color=MUTED)
    style.save(fig, out / "01_headline.png")


# ── 2 & 3. radial per-class accuracy ──────────────────────────────────────────


def fig_radial(m: dict, field: str, names: dict[str, str], title: str, filename: str, out: Path) -> None:
    labels = [label for label in names if class_accuracy(m, field, label)[1]]
    accuracy, support = zip(*(class_accuracy(m, field, label) for label in labels))
    overall = m["labels"][field]["matched"]["micro"]["recall"]
    fig, ax = style.slide(title, f"Share of matched GISD impacts given the same {field} by {NAME}. "
                                 f"Overall: {overall:.0%}.",
                          subplot_kw={"projection": "polar"})
    fig.subplots_adjust(left=0.2, right=0.8, top=0.71, bottom=0.21)

    angles = charts.radar_axes(ax, [f"{names[label]}\nn={n}" for label, n in zip(labels, support)],
                               ["", "50%", "", "100%"], fontsize=12.5)
    ax.fill(charts.closed(angles), charts.closed(accuracy), color=GREEN, alpha=0.22)
    ax.plot(charts.closed(angles), charts.closed(accuracy), color=DARK, linewidth=2.4)
    ax.scatter(angles, accuracy, s=70, color=DARK, edgecolor=SURFACE, linewidth=1.5, zorder=4)
    for angle, value in zip(angles, accuracy):  # inside high points (clear of spoke labels), outside low ones
        ax.text(angle, value - 0.14 if value >= 0.6 else value + 0.14, f"{value:.0%}", ha="center", va="center", fontsize=12,
                fontweight="bold", color=DARK, bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5,
                                                     "alpha": 0.85})
    style.save(fig, out / filename)


# ── 5. severity distance ──────────────────────────────────────────────────────


def fig_severity_distance(cases: pd.DataFrame, out: Path) -> None:
    distance = cases["max_category_distance"]
    bins = [
        ("Exact", (distance == 0).sum(), DARK),
        ("1 category off", (distance == 1).sum(), GREEN),
        ("2 categories off", (distance == 2).sum(), LIGHT),
        ("3+ categories off", (distance >= 3).sum(), LIGHT),
        ("No impact found", distance.isna().sum(), GRID),
    ]
    within_one = bins[0][1] + bins[1][1]
    fig, ax = style.slide(f"{within_one / len(cases):.0%} of papers land within one severity category",
                          f"Per paper, how far the app's most severe EICAT category is from GISD's ({NAME}).")
    fig.subplots_adjust(left=0.1, right=0.9, top=0.74, bottom=0.16)
    x = np.arange(len(bins))
    bars = ax.bar(x, [count for _, count, _ in bins], width=0.62, color=[c for *_, c in bins],
                  edgecolor=[DARK if c == LIGHT else c for *_, c in bins], linewidth=1.2)
    for bar, (_, count, _) in zip(bars, bins):
        ax.text(bar.get_x() + bar.get_width() / 2, count + 0.5, f"{count}  ({count / len(cases):.0%})",
                ha="center", va="bottom", fontsize=14, color=INK)
    ax.set_xticks(x, [label for label, *_ in bins], fontsize=14, color=INK, fontfamily=style.HEADING)
    ax.set_ylabel("Papers")
    ax.set_ylim(0, max(count for _, count, _ in bins) * 1.18)
    ax.grid(axis="x", visible=False)
    ax.spines["left"].set_visible(False)
    style.save(fig, out / "05_severity_distance.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=EVAL / "figures_best")
    parser.add_argument("--bare", action="store_true", help="No in-figure titles, cropped; for slide decks.")
    args = parser.parse_args()

    style.apply(bare=args.bare)
    m, cases = read_metrics(RUN), read_cases(RUN)
    fig_headline(m, cases, args.out)
    fig_radial(m, "mechanism", MECHANISM_LABELS, "Accuracy by impact mechanism", "02_mechanism_radial.png", args.out)
    fig_radial(m, "category", {code: category_label(code) for code in CATEGORY_NAMES}, "Accuracy by EICAT category", "03_category_radial.png", args.out)
    charts.max_category_confusion(m, f"{MODEL} {PROMPT.lower()}", args.out / "04_max_category_confusion.png")
    fig_severity_distance(cases, args.out)


if __name__ == "__main__":
    main()

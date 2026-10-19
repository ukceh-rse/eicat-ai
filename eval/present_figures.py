"""Presentation figures for the 60-paper GISD test-set runs, in OneSTOP brand style.

Reads each run's `metrics.json` (written by `gisd_eval.py`) and writes 16:9 PNGs:

    uv run --project eval eval/present_figures.py

Encoding used throughout: colour = model (Haiku 5.5 dark green, Nova Lite bright green),
fill = prompt (baseline hatched, improved solid).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from matplotlib.patches import Patch

from eicat_eval import charts, style
from eicat_eval.eicat import CATEGORY_NAMES, MECHANISM_LABELS, category_label
from eicat_eval.paths import EVAL
from eicat_eval.runs import class_accuracy, read_metrics
from eicat_eval.style import DARK, GREEN, GRID, INK, MUTED, PALE, SURFACE

# (run directory, model, prompt)
RUNS = [
    ("t60_v0_haiku", "Haiku 5.5", "Baseline"),
    ("t60_v2_haiku", "Haiku 5.5", "Improved"),
    ("t60_v0_novalite", "Nova Lite", "Baseline"),
    ("t60_v2_novalite", "Nova Lite", "Improved"),
]
MODEL_COLOUR = {"Haiku 5.5": DARK, "Nova Lite": GREEN}
CATEGORY_LABELS = {code: category_label(code) for code in CATEGORY_NAMES}


def load() -> dict[tuple[str, str], dict]:
    return {(model, prompt): read_metrics(run) for run, model, prompt in RUNS}


def bar_style(model: str, prompt: str) -> dict:
    colour = MODEL_COLOUR[model]
    if prompt == "Baseline":
        return {"facecolor": SURFACE, "edgecolor": colour, "hatch": "///", "linewidth": 1.6}
    return {"facecolor": colour, "edgecolor": colour, "linewidth": 1.6}


def run_legend(ax, **kwargs) -> None:
    handles = [Patch(**bar_style(model, prompt), label=f"{model} {prompt.lower()}") for _, model, prompt in RUNS]
    ax.legend(handles=handles, ncols=4, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=12,
              handlelength=1.6, handleheight=1.1, **kwargs)


def grouped_bars(ax, groups: list[str], values: dict[tuple[str, str], list[float]]) -> None:
    """One cluster per group, one bar per run, value printed above each bar."""
    width, gap = 0.19, 0.02
    x = np.arange(len(groups))
    for i, (_, model, prompt) in enumerate(RUNS):
        offset = (i - 1.5) * (width + gap) + (0.04 if i >= 2 else -0.04)  # small gap between the two models
        bars = ax.bar(x + offset, values[(model, prompt)], width, **bar_style(model, prompt))
        for bar, value in zip(bars, values[(model, prompt)]):
            ax.text(bar.get_x() + width / 2, value + 0.015, f"{value:.2f}", ha="center", va="bottom",
                    fontsize=11, color=INK)
    ax.set_xticks(x, groups, fontsize=15, color=INK, fontfamily=style.HEADING)
    ax.set_ylim(0, 1)
    ax.set_yticks(np.linspace(0, 1, 6))
    ax.grid(axis="x", visible=False)
    ax.spines["left"].set_visible(False)


# ── 1. detection ──────────────────────────────────────────────────────────────


def fig_detection(metrics: dict, out: Path) -> None:
    keys = {"Precision": "precision", "Recall": "recall", "F2": "f2"}
    values = {run: [m["detection"]["micro"][k] for k in keys.values()] for run, m in metrics.items()}
    best = max(metrics, key=lambda run: metrics[run]["detection"]["micro"]["f2"])
    f2 = [m["detection"]["micro"]["f2"] for m in metrics.values()]
    fig, ax = style.slide(
        f"Every configuration lands at F2 {min(f2):.2f}-{max(f2):.2f}",
        f"Impact detection, micro-averaged over GISD impacts. Best F2: {best[0]} {best[1].lower()} "
        f"({metrics[best]['detection']['micro']['f2']:.2f}).",
    )
    grouped_bars(ax, list(keys), values)
    ax.set_ylabel("Score")
    run_legend(ax)
    style.save(fig, out / "01_detection.png")


# ── 2 & 3. radial per-class accuracy ──────────────────────────────────────────


def radar_panel(ax, labels: list[str], names: dict[str, str], series: dict[str, tuple[list, list]],
                colour: str, title: str) -> None:
    supports = series["Improved"][1]
    angles = charts.radar_axes(ax, [f"{names[label]}\nn={n}" for label, n in zip(labels, supports)],
                               ["", "0.5", "", "1.0"], fontsize=11.5)
    base, _ = series["Baseline"]
    improved, _ = series["Improved"]
    closed_angles = charts.closed(angles)
    ax.plot(closed_angles, charts.closed(base), color=colour, linewidth=2, linestyle=(0, (4, 2.5)), label="Baseline")
    ax.scatter(angles, base, s=46, facecolor=SURFACE, edgecolor=colour, linewidth=1.8, zorder=3)
    ax.fill(closed_angles, charts.closed(improved), color=colour, alpha=0.18)
    ax.plot(closed_angles, charts.closed(improved), color=colour, linewidth=2.4, label="Improved")
    ax.scatter(angles, improved, s=58, color=colour, edgecolor=SURFACE, linewidth=1.5, zorder=4)
    ax.set_title(title, fontfamily=style.HEADING, fontweight="bold", fontsize=18, color=DARK, pad=58)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncols=2, fontsize=12, handlelength=2.6)


def fig_radial(metrics: dict, field: str, names: dict[str, str], title: str, filename: str, out: Path) -> None:
    # Keep classes every run has GISD support for, so each spoke compares like with like.
    labels = [label for label in names if all(class_accuracy(m, field, label)[1] for m in metrics.values())]
    overall = {run: m["labels"][field]["matched"]["micro"]["recall"] for run, m in metrics.items()}
    subtitle = "Share of matched GISD impacts given the same {} by the app (overall: {}).".format(
        field, ", ".join(f"{model} {overall[(model, 'Baseline')]:.2f} → {overall[(model, 'Improved')]:.2f}"
                         for model in MODEL_COLOUR))
    fig, axes = style.slide(title, subtitle, ncols=2, subplot_kw={"projection": "polar"})
    fig.subplots_adjust(left=0.08, right=0.92, top=0.66, bottom=0.25, wspace=0.6)
    for ax, model in zip(axes, MODEL_COLOUR):
        series = {}
        for prompt in ("Baseline", "Improved"):
            pairs = [class_accuracy(metrics[(model, prompt)], field, label) for label in labels]
            series[prompt] = ([p[0] for p in pairs], [p[1] for p in pairs])
        radar_panel(ax, labels, names, series, MODEL_COLOUR[model], model)
    style.save(fig, out / filename)


# ── 4. label accuracy ─────────────────────────────────────────────────────────


def fig_label_accuracy(metrics: dict, out: Path) -> None:
    groups = ["Mechanism", "Category", "Max category\nper paper"]
    values = {
        run: [m["labels"]["mechanism"]["matched"]["micro"]["recall"],
              m["labels"]["category"]["matched"]["micro"]["recall"],
              m["max_category"]["exact_accuracy"]]
        for run, m in metrics.items()
    }
    fig, ax = style.slide(
        "Mechanisms are labelled well; severity is the hard part",
        "Accuracy of EICAT labels on impacts matched to GISD, and of each paper's most severe category.",
    )
    grouped_bars(ax, groups, values)
    ax.set_ylabel("Accuracy")
    run_legend(ax)
    style.save(fig, out / "04_label_accuracy.png")


# ── 5. severity error ─────────────────────────────────────────────────────────


def fig_severity_error(metrics: dict, out: Path) -> None:
    parts = [  # (label, colour, text colour)
        ("Under-rated", GREEN, INK),
        ("No impact found", GRID, INK),
        ("Exact", DARK, SURFACE),
        ("Over-rated", PALE, INK),
    ]
    fig, ax = style.slide(
        "Severity errors cut both ways",
        "Each paper's most severe category from the app against GISD's, as a share of papers per run.",
    )
    fig.subplots_adjust(left=0.2, right=0.86, top=0.74, bottom=0.14)
    y = np.arange(len(RUNS))[::-1]
    for row, (_, model, prompt) in zip(y, RUNS):
        mc = metrics[(model, prompt)]["max_category"]
        n = mc["n"]
        exact = round(mc["exact_accuracy"] * n)
        counts = [mc["n_under"] - mc["n_no_extraction"], mc["n_no_extraction"], exact, mc["n_over"]]
        left = 0.0
        for (label, colour, text), count in zip(parts, counts):
            share = count / n
            ax.barh(row, share, left=left, height=0.62, color=colour, edgecolor=SURFACE, linewidth=2)
            if share >= 0.045:
                ax.text(left + share / 2, row, f"{share:.0%}", ha="center", va="center", fontsize=12.5, color=text)
            left += share
        ax.text(1.02, row, f"{mc['mean_abs_distance']:.2f}", va="center", fontsize=14, color=INK,
                fontfamily=style.HEADING, fontweight="bold")
    ax.text(1.02, len(RUNS) - 0.45, "Mean error\n(categories)", fontsize=11, color=MUTED, va="bottom")
    ax.set_yticks(y, [f"{model}\n{prompt.lower()}" for _, model, prompt in RUNS], fontsize=13, color=INK)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"])
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.legend(handles=[Patch(facecolor=c, label=label) for label, c, _ in parts], ncols=4, loc="lower left",
              bbox_to_anchor=(0, 1.0), fontsize=12)
    style.save(fig, out / "06_severity_error.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=EVAL / "figures_present")
    parser.add_argument("--bare", action="store_true", help="No in-figure titles, cropped; for slide decks.")
    args = parser.parse_args()

    style.apply(bare=args.bare)
    metrics = load()
    fig_detection(metrics, args.out)
    fig_radial(metrics, "mechanism", MECHANISM_LABELS, "Accuracy by impact mechanism",
               "02_mechanism_radial.png", args.out)
    fig_radial(metrics, "category", CATEGORY_LABELS, "Accuracy by EICAT category",
               "03_category_radial.png", args.out)
    fig_label_accuracy(metrics, args.out)
    charts.max_category_confusion(metrics[("Haiku 5.5", "Improved")], "Haiku 5.5 improved",
                                  args.out / "05_max_category_confusion.png")
    fig_severity_error(metrics, args.out)


if __name__ == "__main__":
    main()

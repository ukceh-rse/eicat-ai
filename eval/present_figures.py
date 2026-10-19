"""Presentation figures for the 60-paper GISD test-set runs, in OneSTOP brand style.

Reads each run's `metrics.json` (written by `gisd_eval.py`) and writes 16:9 PNGs:

    uv run --project eval eval/present_figures.py

Encoding used throughout: colour = model (Haiku 5.5 dark green, Nova Lite bright green),
fill = prompt (baseline hatched, improved solid).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch, Rectangle

import present_style as style
from present_style import DARK, GREEN, GRID, INK, LIGHT, MID, MUTED, SURFACE

PALE = "#9BD8A8"  # light step of the brand green, for a third lightness level

RUNS_DIR = Path(__file__).parent / "runs"
# (run directory, model, prompt)
RUNS = [
    ("t60_v0_haiku", "Haiku 5.5", "Baseline"),
    ("t60_v2_haiku", "Haiku 5.5", "Improved"),
    ("t60_v0_novalite", "Nova Lite", "Baseline"),
    ("t60_v2_novalite", "Nova Lite", "Improved"),
]
MODEL_COLOUR = {"Haiku 5.5": DARK, "Nova Lite": GREEN}

CATEGORIES = {  # severity order, as EICAT lists them
    "MC": "Minimal\nConcern",
    "MN": "Minor",
    "MO": "Moderate",
    "MR": "Major",
    "MV": "Massive",
    "DD": "Data\nDeficient",
}
MECHANISMS = {
    "Competition": "Competition",
    "Predation": "Predation",
    "Hybridisation": "Hybridisation",
    "Transmission of disease": "Disease\ntransmission",
    "Poisoning/toxicity": "Poisoning /\ntoxicity",
    "Grazing/herbivory/browsing": "Grazing /\nherbivory",
    "Chemical impact on ecosystem": "Chemical\nimpact",
    "Physical impact on ecosystem": "Physical\nimpact",
    "Structural impact on ecosystem": "Structural\nimpact",
    "Indirect impacts through interactions with other species": "Indirect\n(via other species)",
}


def load() -> dict[tuple[str, str], dict]:
    return {(model, prompt): json.loads((RUNS_DIR / run / "metrics.json").read_text()) for run, model, prompt in RUNS}


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


def class_accuracy(m: dict, field: str, label: str) -> tuple[float, int]:
    """Per-class accuracy on matched pairs: share of GISD impacts of this class given this label."""
    row = m["labels"][field]["matched"]["per_class"].get(label)
    return (row["recall"], row["support"]) if row and row["support"] else (np.nan, 0)


def radar_panel(ax, labels: list[str], names: dict[str, str], series: dict[str, tuple[list, list]],
                colour: str, title: str) -> None:
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    closed = np.append(angles, angles[0])
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0], ["", "0.5", "", "1.0"], fontsize=10, color=MUTED)
    ax.set_rlabel_position(180 / len(labels))
    ax.spines["polar"].set_color(GRID)
    ax.grid(color=GRID, linewidth=0.8)
    supports = series["Improved"][1]
    ax.set_xticks(angles, [f"{names[label]}\nn={n}" for label, n in zip(labels, supports)], fontsize=11.5, color=INK)
    ax.tick_params(axis="x", pad=16)
    for tick, angle in zip(ax.get_xticklabels(), angles):  # anchor side labels away from the ring
        side = np.sin(angle)
        tick.set_horizontalalignment("left" if side > 0.1 else "right" if side < -0.1 else "center")

    base, _ = series["Baseline"]
    improved, _ = series["Improved"]
    ax.plot(closed, np.append(base, base[0]), color=colour, linewidth=2, linestyle=(0, (4, 2.5)), label="Baseline")
    ax.scatter(angles, base, s=46, facecolor=SURFACE, edgecolor=colour, linewidth=1.8, zorder=3)
    ax.fill(closed, np.append(improved, improved[0]), color=colour, alpha=0.18)
    ax.plot(closed, np.append(improved, improved[0]), color=colour, linewidth=2.4, label="Improved")
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


# ── 5. max-category confusion ─────────────────────────────────────────────────


def fig_max_confusion(metrics: dict, run: tuple[str, str], out: Path,
                      filename: str = "05_max_category_confusion.png") -> None:
    confusion = metrics[run]["max_category"]["confusion"]
    labels, matrix = confusion["labels"], np.array(confusion["matrix"])
    order = [label for label in [*CATEGORIES, "none"] if label in labels]
    index = [labels.index(label) for label in order]
    matrix = matrix[np.ix_(index, index)]
    rows = [i for i in range(len(order)) if matrix[i].sum()]  # GISD always gives a category
    cols = [j for j in range(len(order)) if matrix[:, j].sum()]
    matrix = matrix[np.ix_(rows, cols)]
    row_labels = [CATEGORIES[order[i]].replace("\n", " ") for i in rows]
    col_labels = ["No impact\nfound" if order[j] == "none" else CATEGORIES[order[j]] for j in cols]

    share = matrix / matrix.sum(axis=1, keepdims=True)
    cmap = LinearSegmentedColormap.from_list("brand", [SURFACE, LIGHT, GREEN, MID, DARK])
    accuracy = metrics[run]["max_category"]["exact_accuracy"]
    fig, ax = style.slide(
        f"{run[0]} {run[1].lower()}: the most severe category is exact for {accuracy:.0%} of papers",
        "Most severe EICAT category per paper, GISD (rows) against the app (columns). Diagonal = exact; "
        "shading = share of the GISD row.",
    )
    fig.subplots_adjust(left=0.2, right=0.8, top=0.68, bottom=0.14)
    ax.imshow(share, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks(np.arange(len(cols) + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(rows) + 1) - 0.5, minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=3)
    ax.tick_params(which="minor", length=0)
    ax.set_xticks(range(len(cols)), col_labels, fontsize=12, color=INK)
    ax.set_yticks(range(len(rows)), row_labels, fontsize=12, color=INK)
    ax.xaxis.tick_top()
    ax.set_xlabel("App", fontsize=13, labelpad=10)
    ax.xaxis.set_label_position("top")
    ax.set_ylabel("GISD", fontsize=13)
    for i in range(len(rows)):
        for j in range(len(cols)):
            if matrix[i, j]:
                diagonal = order[rows[i]] == order[cols[j]]
                ax.text(j, i, matrix[i, j], ha="center", va="center", fontsize=15,
                        fontweight="bold" if diagonal else "normal",
                        color=SURFACE if share[i, j] > 0.45 else INK)
    for i in range(len(rows)):
        if order[rows[i]] in [order[j] for j in cols]:
            j = [order[c] for c in cols].index(order[rows[i]])
            ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=DARK, linewidth=2.2))
    style.save(fig, out / filename)


# ── 6. severity error ─────────────────────────────────────────────────────────


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
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "figures_present")
    args = parser.parse_args()

    style.apply()
    metrics = load()
    fig_detection(metrics, args.out)
    fig_radial(metrics, "mechanism", MECHANISMS, "Accuracy by impact mechanism",
               "02_mechanism_radial.png", args.out)
    fig_radial(metrics, "category", CATEGORIES, "Accuracy by EICAT category",
               "03_category_radial.png", args.out)
    fig_label_accuracy(metrics, args.out)
    fig_max_confusion(metrics, ("Haiku 5.5", "Improved"), args.out)
    fig_severity_error(metrics, args.out)


if __name__ == "__main__":
    main()

"""Brand-styled chart components shared by the figure scripts. Call `style.apply()` first."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

from eicat_eval import style
from eicat_eval.eicat import CATEGORY_NAMES, category_label
from eicat_eval.style import DARK, GREEN, GRID, INK, LIGHT, MID, MUTED, SURFACE


def closed(values) -> np.ndarray:
    """Values with the first repeated at the end, so a radar line or fill closes on itself."""
    return np.append(values, values[0])


def radar_axes(ax, spoke_labels: list[str], ring_labels: list[str], fontsize: float) -> np.ndarray:
    """Set up a polar axis as a radar chart on a 0-1 scale and return the spoke angles.

    Spokes start at 12 o'clock and run clockwise; `ring_labels` label the rings at 0.25, 0.5, 0.75 and 1.
    Spoke labels on either side are anchored away from the ring so they never overlap it.
    """
    angles = np.linspace(0, 2 * np.pi, len(spoke_labels), endpoint=False)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0], ring_labels, fontsize=10, color=MUTED)
    ax.set_rlabel_position(180 / len(spoke_labels))
    ax.spines["polar"].set_color(GRID)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_xticks(angles, spoke_labels, fontsize=fontsize, color=INK)
    ax.tick_params(axis="x", pad=16)
    for tick, angle in zip(ax.get_xticklabels(), angles):
        side = np.sin(angle)
        tick.set_horizontalalignment("left" if side > 0.1 else "right" if side < -0.1 else "center")
    return angles


def max_category_confusion(metrics: dict, name: str, path: Path) -> None:
    """Heatmap of each case's most severe category, GISD (rows) against the app (columns), for one run.

    `metrics` is the run's `metrics.json`; `name` describes the run in the title. Cells are shaded by
    their share of the GISD row, the diagonal is outlined, and empty rows and columns are dropped.
    """
    confusion = metrics["max_category"]["confusion"]
    labels, matrix = confusion["labels"], np.array(confusion["matrix"])
    order = [label for label in [*CATEGORY_NAMES, "none"] if label in labels]
    index = [labels.index(label) for label in order]
    matrix = matrix[np.ix_(index, index)]
    rows = [i for i in range(len(order)) if matrix[i].sum()]  # GISD always gives a category
    cols = [j for j in range(len(order)) if matrix[:, j].sum()]
    matrix = matrix[np.ix_(rows, cols)]
    row_labels = [category_label(order[i], wrap=False) for i in rows]
    col_labels = ["No impact\nfound" if order[j] == "none" else category_label(order[j]) for j in cols]

    share = matrix / matrix.sum(axis=1, keepdims=True)
    cmap = LinearSegmentedColormap.from_list("brand", [SURFACE, LIGHT, GREEN, MID, DARK])
    accuracy = metrics["max_category"]["exact_accuracy"]
    fig, ax = style.slide(
        f"{name}: the most severe category is exact for {accuracy:.0%} of papers",
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
    style.save(fig, path)

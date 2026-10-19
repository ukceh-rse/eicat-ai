"""Inter-annotator agreement split by EICAT experience, with OneSTOP-styled figures.

Groups come from `annotator_experience.json` (anonymous id -> "Skilled" / "Unskilled"), taken from the
"EICAT experience level" column of the Task 4.4 participation form; it is keyed by anonymous id only.

Reuses the impact clusters from `align_impacts.py` (`iaa_alignment.csv`, no model calls here) and the
agreement statistics in `eicat_eval.agreement`. Group differences are tested exactly, against every way
of splitting the annotators into groups of the same sizes.

    uv run --project eval eval/iaa_experience.py [--bare] [--out DIR] [--metrics FILE]
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import patheffects
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch, Rectangle

from eicat_eval import style
from eicat_eval.agreement import (exact_permutation_p, found_by, krippendorff_alpha, landis_koch, pairwise_jaccard,
                                  presence_matrix)
from eicat_eval.annotators import (coverage as paper_coverage, drop_annotators, load_categories, load_evidence,
                                   load_experience, max_category_matrix, sort_ids)
from eicat_eval.eicat import CATEGORIES, CATEGORY_NAMES
from eicat_eval.paths import EVAL, IAA_ALIGNMENT, IAA_INPUT
from eicat_eval.style import DARK, GREEN, GRID, INK, LIGHT, MUTED, PALE, SURFACE

GROUPS = ("Skilled", "Unskilled")
GROUP_COLOUR = {"Skilled": DARK, "Unskilled": GREEN, "All": PALE}
GROUP_LABEL = {"Skilled": "Experienced", "Unskilled": "Not experienced", "All": "All annotators"}
PAIR_TYPES = ("Skilled-Skilled", "Skilled-Unskilled", "Unskilled-Unskilled")
PAIR_LABEL = {
    "Skilled-Skilled": "Experienced\nwith experienced",
    "Skilled-Unskilled": "Experienced\nwith not experienced",
    "Unskilled-Unskilled": "Not experienced\nwith not experienced",
}


# ── metrics ───────────────────────────────────────────────────────────────────


def detection_alpha(clusters: pd.DataFrame, coverage: dict[str, set[str]], members: list[str]) -> float:
    """Nominal alpha over the presence matrix, restricted to impacts at least one member found."""
    subset = clusters[found_by(clusters).apply(lambda s: bool(s & set(members)))].reset_index(drop=True)
    return krippendorff_alpha(presence_matrix(subset, coverage, members), "nominal")


def category_alpha(matrix: pd.DataFrame, members: list[str]) -> float:
    return krippendorff_alpha(matrix[members].to_numpy(dtype=float), "ordinal")


def group_of(experience: dict[str, str], a: str, b: str) -> str:
    return "-".join(sorted((experience[a], experience[b])))


def group_summary(jaccard: dict, clusters, coverage, matrix, experience: dict[str, str]) -> dict:
    members = {g: sort_ids(a for a, level in experience.items() if level == g) for g in GROUPS}
    members["All"] = sort_ids(experience)
    by_type = {t: [s for (a, b), s in jaccard.items() if group_of(experience, a, b) == t] for t in PAIR_TYPES}
    return {
        "members": members,
        "jaccard": {t: float(np.mean(v)) for t, v in by_type.items()},
        "detection_alpha": {g: detection_alpha(clusters, coverage, m) for g, m in members.items()},
        "category_alpha": {g: category_alpha(matrix, m) for g, m in members.items()},
    }


def consensus_recall(clusters: pd.DataFrame, coverage: dict[str, set[str]], annotators: list[str]) -> dict:
    """Per annotator: share of majority impacts (found by > half of the paper's annotators) they found."""
    found = found_by(clusters)
    majority = clusters.n_annotators > clusters.paper.map(lambda p: len(coverage[p]) / 2)
    recall = {}
    for a in annotators:
        units = [found[i] for i in clusters.index[majority] if a in coverage[clusters.paper[i]]]
        recall[a] = {"found": sum(a in s for s in units), "majority_impacts": len(units)}
    return recall


def compute(input_dir: Path, alignment: Path) -> tuple[dict, dict]:
    experience = load_experience()
    coverage = paper_coverage(load_evidence(input_dir))
    clusters = drop_annotators(pd.read_csv(alignment))  # in case the alignment predates an exclusion
    matrix = max_category_matrix(load_categories(input_dir))
    annotators = sort_ids(experience)
    n_skilled = sum(level == "Skilled" for level in experience.values())

    jaccard = {pair: mean for pair, (mean, n) in pairwise_jaccard(clusters, coverage, annotators).items() if n}
    summary = group_summary(jaccard, clusters, coverage, matrix, experience)

    def jaccard_diff(skilled: set[str]) -> float:
        within = {True: [], False: []}
        for (a, b), s in jaccard.items():
            if (a in skilled) == (b in skilled):
                within[a in skilled].append(s)
        return np.mean(within[True]) - np.mean(within[False])

    def alpha_diff(alpha):
        return lambda skilled: alpha([a for a in annotators if a in skilled]) - \
                               alpha([a for a in annotators if a not in skilled])

    detection = lambda m: detection_alpha(clusters, coverage, m)  # noqa: E731
    category = lambda m: category_alpha(matrix, m)  # noqa: E731
    observed = {
        "jaccard": jaccard_diff(set(summary["members"]["Skilled"])),
        "detection_alpha": summary["detection_alpha"]["Skilled"] - summary["detection_alpha"]["Unskilled"],
        "category_alpha": summary["category_alpha"]["Skilled"] - summary["category_alpha"]["Unskilled"],
    }
    tests = {
        "jaccard": exact_permutation_p(observed["jaccard"], jaccard_diff, annotators, n_skilled),
        "detection_alpha": exact_permutation_p(observed["detection_alpha"], alpha_diff(detection), annotators, n_skilled),
        "category_alpha": exact_permutation_p(observed["category_alpha"], alpha_diff(category), annotators, n_skilled),
    }

    spread = {}
    for paper, row in matrix.iterrows():
        spread[paper] = {g: int(row[m].max() - row[m].min()) if row[m].notna().sum() > 1 else None
                         for g, m in summary["members"].items()}

    metrics = {
        "n_papers": int(matrix.shape[0]),
        "n_impacts": int(len(clusters)),
        "group_sizes": {g: len(summary["members"][g]) for g in (*GROUPS, "All")},
        "experience": experience,
        "jaccard_by_pair_type": summary["jaccard"],
        "detection_alpha": summary["detection_alpha"],
        "category_alpha": summary["category_alpha"],
        "landis_koch": {
            "detection_alpha": {g: landis_koch(v) for g, v in summary["detection_alpha"].items()},
            "category_alpha": {g: landis_koch(v) for g, v in summary["category_alpha"].items()},
        },
        "skilled_minus_unskilled": observed,
        "exact_permutation_p": tests,
        "n_relabellings": len(list(combinations(annotators, n_skilled))),
        "category_spread_by_paper": spread,
        "consensus_recall": consensus_recall(clusters, coverage, annotators),
        "pairwise_jaccard": [{"pair": f"{a}-{b}", "type": group_of(experience, a, b), "jaccard": s}
                             for (a, b), s in jaccard.items()],
    }
    return metrics, {"matrix": matrix, "jaccard": jaccard}


# ── figures ───────────────────────────────────────────────────────────────────


def short(paper: str) -> str:
    return paper.split(" (")[0]


def group_legend(ax, sizes: dict[str, int]) -> None:
    handles = [Patch(facecolor=GROUP_COLOUR[g], label=f"{GROUP_LABEL[g]} (n={sizes[g]})") for g in GROUPS]
    ax.legend(handles=handles, ncols=len(GROUPS), loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=12.5)


def fig_pairwise_heatmap(metrics: dict, data: dict, out: Path) -> None:
    experience = metrics["experience"]
    order = [a for g in GROUPS for a in sort_ids(a for a, level in experience.items() if level == g)]
    n = len(order)
    grid = np.full((n, n), np.nan)
    for (a, b), s in data["jaccard"].items():
        i, j = order.index(a), order.index(b)
        grid[i, j] = grid[j, i] = s
    n_skilled = metrics["group_sizes"]["Skilled"]

    fig, ax = style.slide("Who agrees with whom on which impacts?",
                          "Pairwise Jaccard similarity of the impacts each pair of annotators identified "
                          "(mean over shared papers).")
    fig.subplots_adjust(left=0.3, right=0.72, top=0.76, bottom=0.08)
    cmap = LinearSegmentedColormap.from_list("brand", [SURFACE, LIGHT, GREEN, DARK])
    image = ax.imshow(grid, cmap=cmap, vmin=0, vmax=1)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks(range(n), order, fontsize=11.5, color=INK)
    ax.set_yticks(range(n), order, fontsize=11.5, color=INK)
    ax.xaxis.tick_top()
    for i in range(n):
        for j in range(n):
            if not np.isnan(grid[i, j]):
                ax.text(j, i, f"{grid[i, j]:.2f}"[1:] if grid[i, j] < 1 else "1", ha="center", va="center",
                        fontsize=9, color=SURFACE if grid[i, j] > 0.55 else INK)
    for start, size, group in ((0, n_skilled, "Skilled"), (n_skilled, n - n_skilled, "Unskilled")):
        ax.add_patch(Rectangle((start - 0.5, start - 0.5), size, size, fill=False, edgecolor=GROUP_COLOUR[group],
                               linewidth=3))
        ax.text(-1.4, start + size / 2 - 0.5, GROUP_LABEL[group], rotation=90, ha="right", va="center",
                fontsize=14, fontfamily=style.HEADING, fontweight="bold", color=GROUP_COLOUR[group])
    bar = fig.colorbar(image, ax=ax, fraction=0.04, pad=0.03)
    bar.set_label("Jaccard similarity", color=MUTED)
    bar.outline.set_visible(False)
    style.save(fig, out / "01_pairwise_jaccard.png")


def fig_jaccard_by_pair_type(metrics: dict, out: Path) -> None:
    rows = metrics["pairwise_jaccard"]
    means = metrics["jaccard_by_pair_type"]
    p = metrics["exact_permutation_p"]["jaccard"]
    fig, ax = style.slide(
        f"{'Experienced' if means['Skilled-Skilled'] > means['Unskilled-Unskilled'] else 'Inexperienced'} pairs "
        f"overlap more on impacts{'' if p < 0.05 else ', within chance'}",
        f"Jaccard per annotator pair; bar = mean. Within-group difference: exact permutation p = {p:.3f} "
        f"({metrics['n_relabellings']} relabellings).",
    )
    fig.subplots_adjust(left=0.1, right=0.9, top=0.76, bottom=0.14)
    rng = np.random.default_rng(2026)
    colours = {"Skilled-Skilled": DARK, "Skilled-Unskilled": MUTED, "Unskilled-Unskilled": GREEN}
    for x, kind in enumerate(PAIR_TYPES):
        values = np.array([r["jaccard"] for r in rows if r["type"] == kind])
        ax.scatter(x + rng.uniform(-0.17, 0.17, len(values)), values, s=70, color=colours[kind], alpha=0.85,
                   edgecolor=SURFACE, linewidth=1.2, zorder=3)
        ax.plot([x - 0.3, x + 0.3], [means[kind]] * 2, color=INK, linewidth=3, solid_capstyle="round", zorder=4)
        ax.text(x + 0.34, means[kind], f"{means[kind]:.2f}", va="center", fontsize=16, color=INK,
                fontfamily=style.HEADING, fontweight="bold")
    counts = {t: sum(r["type"] == t for r in rows) for t in PAIR_TYPES}
    ax.set_xticks(range(len(PAIR_TYPES)), [f"{PAIR_LABEL[t]}\n({counts[t]} pairs)" for t in PAIR_TYPES],
                  fontsize=14, color=INK, fontfamily=style.HEADING)
    ax.set_xlim(-0.6, len(PAIR_TYPES) - 0.3)
    ax.set_ylim(-0.02, 1.05)
    ax.set_ylabel("Jaccard similarity")
    ax.grid(axis="x", visible=False)
    ax.spines["left"].set_visible(False)
    style.save(fig, out / "02_jaccard_by_pair_type.png")


def fig_alpha(metrics: dict, out: Path) -> None:
    measures = {"detection_alpha": "Which impacts\nare present", "category_alpha": "Most severe category\nper paper"}
    groups = ("All", *GROUPS)
    sizes = metrics["group_sizes"]
    p = metrics["exact_permutation_p"]
    fig, ax = style.slide(
        f"Agreement is {landis_koch(metrics['detection_alpha']['All']).lower()} on impacts, "
        f"{landis_koch(metrics['category_alpha']['All']).lower()} on severity",
        "Krippendorff's alpha (nominal: impacts; ordinal: category). "
        f"Experienced vs not: p = {p['detection_alpha']:.2f} / {p['category_alpha']:.2f}.",
    )
    fig.subplots_adjust(left=0.08, right=0.8, top=0.76, bottom=0.14)
    bands = [(0, 0.2, "Slight"), (0.2, 0.4, "Fair"), (0.4, 0.6, "Moderate"), (0.6, 0.8, "Substantial"),
             (0.8, 1.0, "Almost perfect")]
    for i, (low, high, name) in enumerate(bands):
        if i % 2:
            ax.axhspan(low, high, color=LIGHT, alpha=0.45, zorder=0, linewidth=0)
        ax.text(1.01, (low + high) / 2, name, transform=ax.get_yaxis_transform(), va="center", fontsize=12,
                color=MUTED)
    width = 0.24
    x = np.arange(len(measures))
    for k, group in enumerate(groups):
        values = [metrics[m][group] for m in measures]
        bars = ax.bar(x + (k - 1) * (width + 0.02), values, width, color=GROUP_COLOUR[group], zorder=2,
                      label=f"{GROUP_LABEL[group]} (n={sizes[group]})")
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + width / 2, max(value, 0) + 0.015, f"{value:.2f}", ha="center", va="bottom",
                    fontsize=13, color=INK, zorder=3)
    ax.set_xticks(x, list(measures.values()), fontsize=15, color=INK, fontfamily=style.HEADING)
    ax.set_ylim(min(0, min(metrics[m][g] for m in measures for g in groups) - 0.05), 1)
    ax.set_ylabel("Krippendorff's alpha")
    ax.grid(False)
    ax.spines["left"].set_visible(False)
    ax.legend(ncols=3, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=12.5)
    style.save(fig, out / "03_alpha_by_group.png")


def fig_category_by_paper(metrics: dict, data: dict, out: Path) -> None:
    matrix = data["matrix"]
    experience = metrics["experience"]
    papers = sorted(matrix.index, key=lambda p: matrix.loc[p].mean())
    fig, ax = style.slide(
        "How severe is each paper's worst impact?",
        "Most severe EICAT category each annotator gave a paper; dot size and number = annotators. "
        "Data Deficient-only ratings excluded.",
    )
    fig.subplots_adjust(left=0.2, right=0.95, top=0.76, bottom=0.1)
    offsets = {"Skilled": 0.2, "Unskilled": -0.2}
    for y, paper in enumerate(papers):
        row = matrix.loc[paper].dropna()
        for group in GROUPS:
            ranks = row[[a for a in row.index if experience[a] == group]].astype(int).value_counts()
            for rank, count in ranks.items():
                ax.scatter(rank, y + offsets[group], s=110 + 95 * count, color=GROUP_COLOUR[group],
                           edgecolor=SURFACE, linewidth=1.5, zorder=3)
                ax.text(rank, y + offsets[group], count, ha="center", va="center", fontsize=11,
                        color=SURFACE if group == "Skilled" else INK, zorder=4)
        if y:
            ax.axhline(y - 0.5, color=GRID, linewidth=0.8)
    ax.set_yticks(range(len(papers)), [short(p) for p in papers], fontsize=13, color=INK)
    ax.set_xticks(range(len(CATEGORIES)), [f"{CATEGORY_NAMES[c]}\n({c})" for c in CATEGORIES], fontsize=12.5, color=INK)
    ax.set_xlim(-0.5, len(CATEGORIES) - 0.5)
    ax.set_ylim(-0.6, len(papers) - 0.4)
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    group_legend(ax, metrics["group_sizes"])
    style.save(fig, out / "04_max_category_by_paper.png")


def fig_consensus_recall(metrics: dict, out: Path) -> None:
    recall = {a: v["found"] / v["majority_impacts"] for a, v in metrics["consensus_recall"].items()
              if v["majority_impacts"]}
    experience = metrics["experience"]
    order = sorted(recall, key=lambda a: (GROUPS.index(experience[a]), -recall[a]))
    means = {g: np.mean([recall[a] for a in order if experience[a] == g]) for g in GROUPS}
    n_majority = max(v["majority_impacts"] for v in metrics["consensus_recall"].values())
    fig, ax = style.slide(
        "Most annotators find most of the majority-agreed impacts",
        f"Share of majority impacts (found by more than half of a paper's annotators; {n_majority} in total) "
        "each annotator identified. Line = group mean.",
    )
    fig.subplots_adjust(left=0.08, right=0.95, top=0.76, bottom=0.14)
    x = np.arange(len(order))
    ax.bar(x, [recall[a] for a in order], 0.66, color=[GROUP_COLOUR[experience[a]] for a in order], zorder=2)
    for i, a in enumerate(order):
        ax.text(i, 0.03, f"{recall[a]:.0%}", ha="center", va="bottom", fontsize=12,
                color=SURFACE if experience[a] == "Skilled" else INK, zorder=4)
    for group in GROUPS:
        idx = [i for i, a in enumerate(order) if experience[a] == group]
        ax.plot([idx[0] - 0.4, idx[-1] + 0.4], [means[group]] * 2, color=INK, linewidth=2,
                linestyle=(0, (4, 2.5)), zorder=3,
                path_effects=[patheffects.withStroke(linewidth=4.5, foreground=SURFACE)])
        ax.text((idx[0] + idx[-1]) / 2, 1.08, f"{GROUP_LABEL[group]}: mean {means[group]:.0%}", ha="center",
                fontsize=14, fontfamily=style.HEADING, fontweight="bold", color=GROUP_COLOUR[group])
    ax.set_xticks(x, order, fontsize=12.5, color=INK)
    ax.set_ylim(0, 1.15)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"])
    ax.grid(axis="x", visible=False)
    ax.spines["left"].set_visible(False)
    style.save(fig, out / "05_consensus_recall.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=IAA_INPUT, help="Directory of annotator spreadsheets.")
    parser.add_argument("--alignment", type=Path, default=IAA_ALIGNMENT, help="Impact clusters from align_impacts.py.")
    parser.add_argument("--metrics", type=Path, default=EVAL / "iaa_experience_metrics.json")
    parser.add_argument("--out", type=Path, default=EVAL / "figures_iaa")
    parser.add_argument("--bare", action="store_true", help="No in-figure titles, cropped; for slide decks.")
    args = parser.parse_args()

    metrics, data = compute(args.input, args.alignment)
    args.metrics.write_text(json.dumps(metrics, indent=2))
    print(f"wrote {args.metrics}")
    for key in ("jaccard_by_pair_type", "detection_alpha", "category_alpha", "exact_permutation_p"):
        print(f"  {key}: " + ", ".join(f"{k} {v:.3f}" for k, v in metrics[key].items()))

    style.apply(bare=args.bare)
    fig_pairwise_heatmap(metrics, data, args.out)
    fig_jaccard_by_pair_type(metrics, args.out)
    fig_alpha(metrics, args.out)
    fig_category_by_paper(metrics, data, args.out)
    fig_consensus_recall(metrics, args.out)


if __name__ == "__main__":
    main()

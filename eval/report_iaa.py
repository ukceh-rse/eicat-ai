"""Turn the IAA metrics files into report-ready figures and a plain-text interpretation.

Run after eval/align_impacts.py and/or eval/category_agreement.py have produced their
metrics files: `uv run --project eval eval/report_iaa.py`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from eicat_eval.agreement import landis_koch
from eicat_eval.annotators import EXCLUDED, annotator_ids, deanonymize
from eicat_eval.eicat import CATEGORIES
from eicat_eval.paths import CATEGORY_METRICS, IAA_FIGURES, IAA_FIGURES_NAMED, IAA_INPUT, IAA_METRICS, IAA_REPORT


def plot_pairwise_heatmap(metrics: dict, output: Path, labels: dict[str, str] | None = None) -> None:
    annotators = metrics["annotators"]
    n = len(annotators)
    idx = {a: i for i, a in enumerate(annotators)}
    matrix = np.full((n, n), np.nan)
    np.fill_diagonal(matrix, 1.0)
    for p in metrics["pairwise_jaccard"]:
        a, b = p["pair"].split("-")
        matrix[idx[a], idx[b]] = matrix[idx[b], idx[a]] = p["jaccard"]

    display = [labels.get(a, a) for a in annotators] if labels else annotators
    fig, ax = plt.subplots(figsize=(6, 5.5))
    im = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(n), display)
    ax.set_yticks(range(n), display)
    for i in range(n):
        for j in range(n):
            if not np.isnan(matrix[i, j]):
                ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", color="white" if matrix[i, j] > 0.6 else "black", fontsize=8)

    fig.colorbar(im, ax=ax, label="Jaccard index")
    ax.set_title(f"Pairwise Jaccard agreement ({metrics['n_papers']} papers, {n} annotators)")
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def plot_agreement_distribution(metrics: dict, output: Path) -> None:
    dist = metrics["agreement_distribution"]
    xs = sorted(int(k) for k in dist)
    ys = [dist[str(x)] for x in xs]

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.bar(xs, ys)
    ax.bar_label(ax.containers[0])
    ax.set_xticks(xs)
    ax.set_xlabel("Number of annotators who identified the impact")
    ax.set_ylabel("Number of distinct impacts")
    ax.set_title(f"Agreement on impact presence ({metrics['n_impacts']} impacts, {metrics['n_papers']} papers)")
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def plot_category_heatmap(metrics: dict, output: Path, labels: dict[str, str] | None = None) -> None:
    papers = list(metrics["matrix"])
    annotators = metrics["annotators"]
    matrix = np.array([[metrics["matrix"][p].get(a) for a in annotators] for p in papers], dtype=float)

    display = [labels.get(a, a) for a in annotators] if labels else annotators
    fig, ax = plt.subplots(figsize=(8.5, 1 + 0.6 * len(papers)))
    im = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=len(CATEGORIES) - 1)
    ax.set_xticks(range(len(annotators)), display)
    ax.set_yticks(range(len(papers)), [p.split(" (")[0] for p in papers])
    for i in range(len(papers)):
        for j in range(len(annotators)):
            v = matrix[i, j]
            if not np.isnan(v):
                ax.text(j, i, CATEGORIES[int(v)], ha="center", va="center", color="white" if v > 2 else "black", fontsize=8)

    cbar = fig.colorbar(im, ax=ax, ticks=range(len(CATEGORIES)))
    cbar.ax.set_yticklabels(CATEGORIES)
    ax.set_title(f"Maximum EICAT category per paper ({metrics['n_papers']} papers, {len(annotators)} annotators)")
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def presence_summary(metrics: dict) -> list[str]:
    js = metrics["jaccard_summary"]
    alpha = metrics["krippendorff_alpha"]
    dist = metrics["agreement_distribution"]
    total = metrics["n_impacts"]
    singleton = dist.get("1", 0)
    unanimous = sum(p["unanimous"] for p in metrics.get("per_paper", []))

    return [
        f"# IAA summary ({metrics['n_papers']} papers, {len(metrics['annotators'])} annotators, batch_a)",
        "",
        "## Which impacts are present",
        "",
        f"- {total} distinct impacts identified across {metrics['n_papers']} papers.",
        f"- Mean pairwise Jaccard agreement: {js['mean']:.2f} (median {js['median']:.2f}, sd {js['std']:.2f}), "
        f"ranging from {js['min']['jaccard']:.2f} ({js['min']['pair']}) to {js['max']['jaccard']:.2f} ({js['max']['pair']}).",
        f"- Krippendorff's alpha (nominal, presence/absence): {alpha:.2f}, **{landis_koch(alpha)}** agreement "
        "on the Landis & Koch (1977) scale used in site/eval-protocol.qmd.",
        f"- {singleton}/{total} impacts ({singleton / total * 100:.0f}%) were flagged by only one annotator; "
        f"{unanimous}/{total} ({unanimous / total * 100:.0f}%) were unanimous among everyone who covered that paper.",
        "",
        f"Agreement on which impacts are present in a paper is {landis_koch(alpha).lower()}, even before EICAT "
        f"category or mechanism labels enter the picture. The gap between the Jaccard figures (mean {js['mean']:.2f}) "
        f"and Krippendorff's alpha ({alpha:.2f}) is expected: alpha corrects for chance agreement and is pulled down "
        "by impacts only one annotator flagged, mostly cases where one person split or noticed something others "
        "didn't.",
    ]


def category_summary(metrics: dict, presence_alpha: float) -> list[str]:
    alpha = metrics["krippendorff_alpha"]
    n, unanimous = metrics["n_papers"], metrics["unanimous_papers"]

    return [
        "## Maximum EICAT category per paper",
        "",
        f"- Krippendorff's alpha (ordinal, max category per paper): {alpha:.2f}, **{landis_koch(alpha)}** agreement "
        "on the Landis & Koch (1977) scale.",
        f"- {unanimous}/{n} papers had unanimous agreement on the maximum category; mean spread of "
        f"{metrics['mean_spread']:.1f} category steps where annotators disagreed.",
        "",
        "Even the single most consequential number in an EICAT assessment, the worst-case category found in a "
        f"paper, was unanimous on {f'only {unanimous} of {n}' if unanimous else 'none of the'} papers in this batch. "
        f"Agreement is {'better' if alpha > presence_alpha else 'no better'} than on impact presence "
        f"(alpha {presence_alpha:.2f}, {landis_koch(presence_alpha)}), but still leaves room for a system to land "
        "within human variability without matching any one gold-standard annotator's category exactly.",
    ]


def make_figures(metrics: dict, category_metrics: dict | None, output_dir: Path, labels: dict[str, str] | None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_pairwise_heatmap(metrics, output_dir / "iaa_pairwise_jaccard.png", labels)
    plot_agreement_distribution(metrics, output_dir / "iaa_agreement_distribution.png")
    if category_metrics is not None:
        plot_category_heatmap(category_metrics, output_dir / "iaa_max_category.png", labels)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metrics", type=Path, default=IAA_METRICS)
    ap.add_argument("--category-metrics", type=Path, default=CATEGORY_METRICS)
    ap.add_argument("--batch-dir", type=Path, default=IAA_INPUT)
    ap.add_argument("--output-dir", type=Path, default=IAA_FIGURES, help="Anonymized figures, safe to publish.")
    ap.add_argument("--named-output-dir", type=Path, default=IAA_FIGURES_NAMED, help="Same figures with real initials, local debugging only.")
    ap.add_argument("--summary", type=Path, default=IAA_REPORT)
    args = ap.parse_args()

    metrics = json.loads(args.metrics.read_text())
    category_metrics = json.loads(args.category_metrics.read_text()) if args.category_metrics.exists() else None

    make_figures(metrics, category_metrics, args.output_dir, labels=None)
    make_figures(metrics, category_metrics, args.named_output_dir, labels=deanonymize())

    lines = presence_summary(metrics)
    if category_metrics is not None:
        lines += [""] + category_summary(category_metrics, metrics["krippendorff_alpha"])

    text = "\n".join(lines)
    args.summary.write_text(text + "\n")
    print(text)
    print(f"\nWrote anonymized figures to {args.output_dir}, named figures to {args.named_output_dir}, summary to {args.summary}")

    if args.batch_dir.exists():
        missing = set(annotator_ids(args.batch_dir)) - set(metrics["annotators"]) - EXCLUDED
        if missing:
            print(f"\nNOTE: {args.batch_dir} has annotator file(s) not covered by the impact-alignment run: {sorted(missing)}. Re-run align_impacts.py to include them.")


if __name__ == "__main__":
    main()

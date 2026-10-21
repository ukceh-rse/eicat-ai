"""Inter-annotator agreement on the EICAT category and mechanism of impacts annotators both found.

Reuses the impact clusters from `align_impacts.py` (`iaa_alignment.csv`, no model calls here): every
impact found by at least two annotators is a unit, and each annotator's label for it is the set of
categories (or mechanisms) on their quotes in the cluster. Pairs where either side left the label blank
are skipped.

Every pair of annotators who labelled the same impact gets one outcome:
- same: identical labels;
- overlapping: they share a label but one gave an extra one (e.g. "Competition" vs "Competition + Predation");
- otherwise, for mechanism, different; for category, one step apart, Data Deficient vs a severity, or two or
  more steps apart (comparing each side's most severe category).

Outcomes are reported for all pairs and for pairs within each experience group, alongside Krippendorff's
alpha over all annotators.

    uv run --project eval eval/iaa_labels.py [--bare] [--out DIR] [--metrics FILE]
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from eicat_eval import style
from eicat_eval.agreement import krippendorff_alpha, landis_koch
from eicat_eval.annotators import drop_annotators, load_experience, load_labels, sort_ids
from eicat_eval.eicat import DATA_DEFICIENT, SEVERITY
from eicat_eval.paths import EVAL, IAA_ALIGNMENT, IAA_INPUT
from eicat_eval.style import DARK, GREEN, INK, MUTED, PALE, SURFACE

FIELDS = {"mechanisms": "Impact mechanism", "category": "EICAT category"}
GROUPS = {"Skilled": "Experienced pairs", "Unskilled": "Not experienced pairs", "All": "All pairs"}
OUTCOMES = {  # per field, in display order: outcome -> (legend label, colour)
    "mechanisms": {
        "same": ("Same mechanism", DARK),
        "overlapping": ("Same, plus an extra one", GREEN),
        "different": ("Different mechanism", MUTED),
    },
    "category": {
        "same": ("Same category", DARK),
        "overlapping": ("Same, plus an extra one", GREEN),
        "one_step": ("One step apart", PALE),
        "dd": ("Data Deficient vs a severity", "#C9D1CC"),
        "further": ("Two or more steps apart", MUTED),
    },
}


# ── metrics ───────────────────────────────────────────────────────────────────


def shared_impacts(clusters: pd.DataFrame, labels: pd.DataFrame) -> list[dict]:
    """Per impact found by two or more annotators: paper, and annotator -> label set for each field."""
    by_quote = labels.set_index("quote_id")
    units = []
    for _, row in clusters[clusters.n_annotators >= 2].iterrows():
        given = {field: {} for field in FIELDS}
        for quote in row.quote_ids.split(","):
            annotator = quote.rsplit("-", 1)[0]
            category, mechanisms = by_quote.loc[quote, ["category", "mechanisms"]]
            given["category"].setdefault(annotator, set()).update({category} if category else set())
            given["mechanisms"].setdefault(annotator, set()).update(mechanisms)
        units.append({"paper": row.paper, **{f: {a: frozenset(s) for a, s in v.items() if s} for f, v in given.items()}})
    return units


def outcome(field: str, x: frozenset, y: frozenset) -> str:
    """How two annotators' labels for one impact relate (see the module docstring)."""
    if x == y:
        return "same"
    if x & y:
        return "overlapping"
    if field == "mechanisms":
        return "different"
    x, y = x - {DATA_DEFICIENT}, y - {DATA_DEFICIENT}
    if not x or not y:
        return "dd"
    return "one_step" if abs(max(map(SEVERITY.get, x)) - max(map(SEVERITY.get, y))) <= 1 else "further"


def pair_outcomes(units: list[dict], field: str, experience: dict[str, str]) -> dict:
    """Outcome counts and shares per group: all pairs, and pairs within each experience group."""
    counts = {g: {o: 0 for o in OUTCOMES[field]} for g in GROUPS}
    for unit in units:
        for (a, x), (b, y) in combinations(unit[field].items(), 2):
            result = outcome(field, x, y)
            counts["All"][result] += 1
            if experience[a] == experience[b]:
                counts[experience[a]][result] += 1
    return {g: {"pairs": sum(c.values()), "counts": c, "shares": {o: n / sum(c.values()) for o, n in c.items()}}
            for g, c in counts.items()}


def nominal_alpha(units: list[dict], field: str, annotators: list[str]) -> float:
    """Krippendorff's alpha with each distinct label set as one nominal value."""
    codes = {}
    matrix = [[codes.setdefault(unit[field][a], len(codes)) if a in unit[field] else np.nan for a in annotators]
              for unit in units]
    return krippendorff_alpha(np.array(matrix, dtype=float), "nominal")


def compute(input_dir: Path, alignment: Path) -> dict:
    clusters = drop_annotators(pd.read_csv(alignment))
    units = shared_impacts(clusters, load_labels(input_dir))
    experience = load_experience()
    annotators = sort_ids({a for unit in units for field in FIELDS for a in unit[field]})
    alpha = {field: nominal_alpha(units, field, annotators) for field in FIELDS}
    return {
        "n_shared_impacts": len(units),
        "n_papers": len({unit["paper"] for unit in units}),
        "alpha": alpha,
        "landis_koch": {field: landis_koch(value) for field, value in alpha.items()},
        "pair_outcomes": {field: pair_outcomes(units, field, experience) for field in FIELDS},
    }


# ── figures ───────────────────────────────────────────────────────────────────


def fig_pair_outcomes(metrics: dict, out: Path) -> None:
    """Per field, a 100% bar per group splitting annotator pairs by how their labels for an impact relate."""
    outcomes = metrics["pair_outcomes"]
    fig, axes = style.slide(
        "Annotators agree on mechanism; on category they are usually close",
        f"Pairs of annotators who found the same impact ({metrics['n_shared_impacts']} impacts, "
        f"{metrics['n_papers']} papers): how their labels compare.",
        nrows=2,
    )
    fig.subplots_adjust(left=0.2, right=0.97, top=0.8, bottom=0.06, hspace=0.75)
    groups = ("Skilled", "Unskilled")
    for ax, field in zip(axes, FIELDS):
        for row, group in enumerate(groups):
            left = 0.0
            for key, (_, colour) in OUTCOMES[field].items():
                share = outcomes[field][group]["shares"][key]
                ax.barh(row, share, left=left, color=colour, height=0.62, edgecolor=SURFACE, linewidth=1.5)
                if share >= 0.06:
                    ax.text(left + share / 2, row, f"{share:.0%}", ha="center", va="center", fontsize=13,
                            fontweight="bold", color=SURFACE if colour in (DARK, GREEN, MUTED) else INK)
                left += share
        ax.set_yticks(range(len(groups)),
                      [f"{GROUPS[g]}\n({outcomes[field][g]['pairs']} pairs)" for g in groups], fontsize=13, color=INK)
        ax.invert_yaxis()
        ax.set_xlim(0, 1)
        ax.set_xticks([])
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(f"{FIELDS[field]}: {outcomes[field]['All']['shares']['same']:.0%} of all pairs give the same",
                     loc="left", fontsize=17, fontfamily=style.HEADING, fontweight="bold", color=DARK, pad=44)
        ax.legend(handles=[Patch(facecolor=colour, label=label) for label, colour in OUTCOMES[field].values()],
                  ncols=len(OUTCOMES[field]), loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=12,
                  handlelength=1.2, columnspacing=1.4)
    style.save(fig, out / "06_label_agreement.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=IAA_INPUT, help="Directory of annotator spreadsheets.")
    parser.add_argument("--alignment", type=Path, default=IAA_ALIGNMENT, help="Impact clusters from align_impacts.py.")
    parser.add_argument("--metrics", type=Path, default=EVAL / "iaa_label_metrics.json")
    parser.add_argument("--out", type=Path, default=EVAL / "figures_iaa")
    parser.add_argument("--bare", action="store_true", help="No in-figure titles, cropped; for slide decks.")
    args = parser.parse_args()

    metrics = compute(args.input, args.alignment)
    args.metrics.write_text(json.dumps(metrics, indent=2))
    print(f"wrote {args.metrics}")
    for field in FIELDS:
        print(f"  {field}: alpha {metrics['alpha'][field]:.2f} ({metrics['landis_koch'][field]})")
        for group, result in metrics["pair_outcomes"][field].items():
            print(f"    {group} ({result['pairs']} pairs): "
                  + ", ".join(f"{o} {s:.0%}" for o, s in result["shares"].items()))

    style.apply(bare=args.bare)
    fig_pair_outcomes(metrics, args.out)


if __name__ == "__main__":
    main()

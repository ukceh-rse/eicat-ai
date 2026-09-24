"""Do annotators agree on the maximum EICAT category found in each paper?

A second IAA angle, independent of the LLM-based impact alignment in align_impacts.py:
for each paper, take each annotator's most severe (highest-ranked) EICAT category and
measure how much annotators agree on it. Pure pandas, no LLM calls needed.
Run: `uv run --project eval eval/category_agreement.py --input eval-data/batch_a`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import krippendorff
import numpy as np
import pandas as pd

from anonymize import anonymize, sort_ids

PAPER_COL = "Species/Reference Text"
CATEGORY_COL = "EICAT Category"
CATEGORIES = ["Minimal Concern", "Minor", "Moderate", "Major", "Massive"]
RANK = {c: i for i, c in enumerate(CATEGORIES)}
ABBR = {"Minimal Concern": "MC", "Minor": "MN", "Moderate": "MO", "Major": "MR", "Massive": "MV"}


def load(input_dir: Path) -> pd.DataFrame:
    files = sorted(list(input_dir.glob("*.xlsx")) + list(input_dir.glob("*.csv")))
    ids = anonymize({f.stem for f in files})

    rows = []
    for f in files:
        read = pd.read_csv if f.suffix == ".csv" else pd.read_excel
        df = read(f, usecols=[PAPER_COL, CATEGORY_COL])
        df[PAPER_COL] = df[PAPER_COL].ffill()
        for paper, cat in zip(df[PAPER_COL], df[CATEGORY_COL]):
            if pd.isna(paper) or pd.isna(cat):
                continue
            # some annotators write "MC - Minimal Concern" instead of "Minimal Concern"
            category = str(cat).split(" - ")[-1].strip()
            if category not in RANK and category != "Data Deficient":
                print(f"NOTE: {f.name} has an unrecognised EICAT Category value {cat!r}, excluding it from the ranking.")
                continue
            rows.append({"annotator": ids[f.stem], "paper": str(paper).split(" / ")[0].strip(), "category": category})
    return pd.DataFrame(rows)


def max_category_matrix(data: pd.DataFrame) -> pd.DataFrame:
    """Papers x annotators, cell = highest category rank assigned (nan = no rated category)."""
    ranked = data.assign(rank=data.category.map(RANK)).dropna(subset=["rank"])
    return ranked.groupby(["paper", "annotator"])["rank"].max().unstack("annotator")


def report(data: pd.DataFrame, matrix: pd.DataFrame, metrics_path: Path) -> dict:
    alpha = float(krippendorff.alpha(reliability_data=matrix.to_numpy(dtype=float).T, level_of_measurement="ordinal"))

    per_paper = []
    for paper, row in matrix.iterrows():
        seen = row.dropna()
        per_paper.append(
            {
                "paper": paper,
                "n_annotators": int(len(seen)),
                "categories": sorted({CATEGORIES[int(r)] for r in seen}),
                "unanimous": bool(seen.nunique() <= 1),
                "spread": int(seen.max() - seen.min()) if len(seen) else 0,
            }
        )

    dd_counts = data.groupby("paper").apply(lambda g: int((g.category == "Data Deficient").sum()), include_groups=False)

    metrics = {
        "n_papers": len(matrix),
        "annotators": sort_ids(data.annotator.unique()),
        "krippendorff_alpha": alpha,
        "unanimous_papers": sum(p["unanimous"] for p in per_paper),
        "mean_spread": float(np.mean([p["spread"] for p in per_paper])),
        "per_paper": per_paper,
        "data_deficient_counts": dd_counts.to_dict(),
        "matrix": {paper: {a: (None if pd.isna(v) else int(v)) for a, v in row.items()} for paper, row in matrix.iterrows()},
    }
    metrics_path.write_text(json.dumps(metrics, indent=2))

    print(f"\nMaximum EICAT category per paper, {metrics['n_papers']} papers, {len(metrics['annotators'])} annotators")
    print(f"Krippendorff's alpha (ordinal): {alpha:.2f}")
    print(f"{metrics['unanimous_papers']}/{metrics['n_papers']} papers unanimous; mean spread {metrics['mean_spread']:.1f} category steps")
    return metrics


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=Path("eval-data/batch_a"))
    ap.add_argument("--metrics", type=Path, default=Path("eval/category_metrics.json"))
    args = ap.parse_args()

    data = load(args.input)
    matrix = max_category_matrix(data)
    report(data, matrix, args.metrics)
    print(f"\nWrote metrics to {args.metrics}")


if __name__ == "__main__":
    main()

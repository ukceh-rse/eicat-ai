"""Do annotators agree on the maximum EICAT category found in each paper?

A second IAA angle, independent of the LLM-based impact alignment in align_impacts.py:
for each paper, take each annotator's most severe (highest-ranked) EICAT category and
measure how much annotators agree on it. Pure pandas, no LLM calls needed.

    uv run --project eval eval/category_agreement.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from eicat_eval.agreement import krippendorff_alpha
from eicat_eval.annotators import load_categories, max_category_matrix, sort_ids
from eicat_eval.eicat import CATEGORIES, CATEGORY_NAMES
from eicat_eval.paths import CATEGORY_METRICS, IAA_INPUT


def report(data: pd.DataFrame, matrix: pd.DataFrame, metrics_path: Path) -> dict:
    alpha = krippendorff_alpha(matrix.to_numpy(dtype=float), "ordinal")

    per_paper = []
    for paper, row in matrix.iterrows():
        seen = row.dropna()
        per_paper.append(
            {
                "paper": paper,
                "n_annotators": int(len(seen)),
                "categories": sorted({CATEGORY_NAMES[CATEGORIES[int(r)]] for r in seen}),
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
    ap.add_argument("--input", type=Path, default=IAA_INPUT, help="Directory of annotator spreadsheets.")
    ap.add_argument("--metrics", type=Path, default=CATEGORY_METRICS)
    args = ap.parse_args()

    data = load_categories(args.input)
    matrix = max_category_matrix(data)
    report(data, matrix, args.metrics)
    print(f"\nWrote metrics to {args.metrics}")


if __name__ == "__main__":
    main()

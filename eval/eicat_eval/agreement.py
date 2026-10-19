"""Inter-annotator agreement statistics.

Detection agreement works on an impact alignment (`align_impacts.py` output): one row per distinct
impact (cluster) with its `paper` and the comma-separated `annotators` who identified it, plus a
coverage map of which annotators annotated each paper (`annotators.coverage`). An annotator who did
not annotate a paper counts as missing for its impacts, not as having missed them.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations

import krippendorff
import numpy as np
import pandas as pd


def found_by(clusters: pd.DataFrame) -> pd.Series:
    """The set of annotators who identified each impact."""
    return clusters.annotators.str.split(",").apply(set)


def presence_matrix(clusters: pd.DataFrame, coverage: dict[str, set[str]], annotators: list[str]) -> np.ndarray:
    """Impacts (rows) x annotators (columns): 1 = identified, 0 = annotated the paper but missed it, nan = did not
    annotate the paper."""
    found = found_by(clusters)
    rows = [
        [1.0 if a in found.iloc[i] else (0.0 if a in coverage[clusters.paper.iloc[i]] else np.nan) for a in annotators]
        for i in range(len(clusters))
    ]
    return np.array(rows)


def pairwise_jaccard(clusters: pd.DataFrame, coverage: dict[str, set[str]],
                     annotators: list[str]) -> dict[tuple[str, str], tuple[float, int]]:
    """(a, b) -> (mean Jaccard of the impacts each found, number of papers it is averaged over), for every pair.

    The mean runs over papers both annotators covered and at least one found an impact in, which keeps it
    robust to partial coverage. A pair with no such paper scores nan over 0 papers.
    """
    found = found_by(clusters)
    scores = {}
    for a, b in combinations(annotators, 2):
        per_paper = []
        for paper, group in clusters.groupby("paper"):
            if not {a, b} <= coverage[paper]:
                continue
            found_a = {i for i in group.index if a in found[i]}
            found_b = {i for i in group.index if b in found[i]}
            if found_a | found_b:
                per_paper.append(len(found_a & found_b) / len(found_a | found_b))
        scores[(a, b)] = (sum(per_paper) / len(per_paper) if per_paper else float("nan"), len(per_paper))
    return scores


def krippendorff_alpha(units_by_raters: np.ndarray, level: str) -> float:
    """Krippendorff's alpha for a units x raters matrix (nan = rater did not rate the unit).

    `level` is the level of measurement: "nominal" for presence/absence, "ordinal" for ranked categories.
    """
    return float(krippendorff.alpha(reliability_data=np.asarray(units_by_raters, dtype=float).T,
                                    level_of_measurement=level))


def landis_koch(value: float) -> str:
    """Landis & Koch (1977) interpretation band for a chance-corrected agreement coefficient."""
    if value < 0:
        return "Poor"
    if value <= 0.20:
        return "Slight"
    if value <= 0.40:
        return "Fair"
    if value <= 0.60:
        return "Moderate"
    if value <= 0.80:
        return "Substantial"
    return "Almost perfect"


def exact_permutation_p(observed: float, statistic: Callable[[set[str]], float], members: list[str],
                        group_size: int) -> float:
    """Two-sided exact p-value for a difference between two groups of `members`.

    `statistic(group)` computes the group difference when `group` (of `group_size` members) is the first
    group and everyone else the second. The p-value is the share of all such splits whose |statistic| is at
    least |`observed`|; there are C(len(members), group_size) of them, so keep the groups small.
    """
    diffs = [statistic(set(group)) for group in combinations(members, group_size)]
    return float(np.mean(np.abs(diffs) >= abs(observed) - 1e-12))

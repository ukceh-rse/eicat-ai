import math

import numpy as np
import pandas as pd
import pytest

from eicat_eval.agreement import exact_permutation_p, krippendorff_alpha, landis_koch, pairwise_jaccard, presence_matrix

# Two papers. On P1, A1 and A2 both found impact 0 and only A1 found impact 1; A3 did not annotate P1.
# On P2, everyone annotated and A2 and A3 found impact 2.
CLUSTERS = pd.DataFrame({
    "paper": ["P1", "P1", "P2"],
    "annotators": ["A1,A2", "A1", "A2,A3"],
})
COVERAGE = {"P1": {"A1", "A2"}, "P2": {"A1", "A2", "A3"}}


def test_presence_matrix_marks_found_missed_and_not_annotated():
    matrix = presence_matrix(CLUSTERS, COVERAGE, ["A1", "A2", "A3"])
    expected = np.array([[1, 1, np.nan], [1, 0, np.nan], [0, 1, 1]], dtype=float)
    np.testing.assert_array_equal(matrix, expected)


def test_pairwise_jaccard_averages_over_shared_papers():
    scores = pairwise_jaccard(CLUSTERS, COVERAGE, ["A1", "A2", "A3"])
    mean, n = scores[("A1", "A2")]
    assert mean == pytest.approx((0.5 + 0.0) / 2) and n == 2  # P1: {0, 1} vs {0}; P2: {} vs {2}
    assert scores[("A2", "A3")] == (1.0, 1)  # only P2 is shared
    assert scores[("A1", "A3")] == (0.0, 1)


def test_pairwise_jaccard_without_shared_papers_is_nan():
    mean, n = pairwise_jaccard(CLUSTERS, {"P1": {"A1"}, "P2": {"A2"}}, ["A1", "A2"])[("A1", "A2")]
    assert math.isnan(mean) and n == 0


def test_krippendorff_alpha_perfect_and_nominal():
    perfect = np.array([[1, 1], [0, 0], [1, 1]], dtype=float)
    assert krippendorff_alpha(perfect, "nominal") == pytest.approx(1.0)
    assert krippendorff_alpha(np.array([[1, 0], [0, 1], [1, 1], [0, 0]], dtype=float), "nominal") < 0.5


@pytest.mark.parametrize("value, band", [(-0.1, "Poor"), (0.2, "Slight"), (0.39, "Fair"), (0.6, "Moderate"),
                                         (0.69, "Substantial"), (0.81, "Almost perfect")])
def test_landis_koch_bands(value, band):
    assert landis_koch(value) == band


def test_exact_permutation_p_counts_splits_at_least_as_extreme():
    values = {"a": 10, "b": 9, "c": 1, "d": 0}

    def difference(group):
        inside = [v for k, v in values.items() if k in group]
        outside = [v for k, v in values.items() if k not in group]
        return np.mean(inside) - np.mean(outside)

    observed = difference({"a", "b"})  # the most extreme of the 6 splits, with its mirror image {c, d}
    assert exact_permutation_p(observed, difference, list(values), 2) == pytest.approx(2 / 6)

import pandas as pd
import pytest

from eicat_eval import annotators
from eicat_eval.annotators import (CATEGORY_COL, EVIDENCE_COL, PAPER_COL, drop_annotators, load_categories,
                                   load_evidence, max_category_matrix, sort_ids)


@pytest.fixture
def sheets(tmp_path, monkeypatch):
    """Two annotator sheets, `ab` -> A1 and `cd` -> A7 (excluded), without touching the real id mapping."""
    monkeypatch.setattr(annotators, "anonymize", lambda stems: {"ab": "A1", "cd": "A7"})
    pd.DataFrame({
        PAPER_COL: ["Toad / Smith 2020", None, "Crow"],
        EVIDENCE_COL: ["eats beetles", None, "displaces mynas"],
        CATEGORY_COL: ["MN - Minor", "Major", "Data Deficient"],
    }).to_csv(tmp_path / "ab.csv", index=False)
    pd.DataFrame({PAPER_COL: ["Toad"], EVIDENCE_COL: ["x"], CATEGORY_COL: ["Massive"]}).to_csv(tmp_path / "cd.csv",
                                                                                                index=False)
    return tmp_path


def test_sort_ids_is_numeric():
    assert sort_ids(["A10", "A2", "A1"]) == ["A1", "A2", "A10"]


def test_load_evidence_fills_papers_and_skips_excluded(sheets):
    evidence = load_evidence(sheets)
    assert evidence.to_dict("records") == [
        {"annotator": "A1", "paper": "Toad", "quote_id": "A1-0", "evidence": "eats beetles"},
        {"annotator": "A1", "paper": "Crow", "quote_id": "A1-1", "evidence": "displaces mynas"},
    ]


def test_load_categories_normalises_names(sheets):
    categories = load_categories(sheets)
    assert list(categories.category) == ["Minor", "Major", "Data Deficient"]
    assert list(categories.paper) == ["Toad", "Toad", "Crow"]


def test_max_category_matrix_ranks_and_ignores_data_deficient(sheets):
    matrix = max_category_matrix(load_categories(sheets))
    assert matrix.loc["Toad", "A1"] == 3  # Major, ranked MC=0 ... MV=4
    assert "Crow" not in matrix.index  # only Data Deficient there


def test_drop_annotators_removes_ids_quotes_and_orphan_impacts():
    clusters = pd.DataFrame({"paper": ["P", "P"], "annotators": ["A1,A7", "A7"], "n_annotators": [2, 1],
                             "quote_ids": ["A1-0,A7-3", "A7-4"]})
    kept = drop_annotators(clusters)
    assert kept.to_dict("records") == [{"paper": "P", "annotators": "A1", "n_annotators": 1, "quote_ids": "A1-0"}]

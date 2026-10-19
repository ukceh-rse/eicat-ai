import pandas as pd

from eicat_eval.gisd import canonical_mechanism, gold_impacts, merge_countries


def test_merge_countries_joins_duplicate_impacts():
    impact = {"Impact mechanism": "Predation", "EICAT Category": "MN", "Evidence for EICAT impact category": "eats",
              "Impacted native species": "Beetle"}
    rows = pd.DataFrame([
        {**impact, "Countries of impact": "Spain", "Species": "Toad"},
        {**impact, "Countries of impact": "Italy", "Species": "Toad"},
        {**impact, "Countries of impact": "Spain", "Species": "Toad"},
        {**impact, "EICAT Category": "MO", "Countries of impact": "France", "Species": "Toad"},
    ])
    merged = merge_countries(rows)
    assert list(merged.columns) == list(rows.columns)
    assert list(merged["Countries of impact"]) == ["Spain, Italy", "France"]


def test_gold_impacts_keeps_file_order_per_case():
    gold = pd.DataFrame({"case_id": ["b", "a", "b"], "value": [1, 2, 3]})
    cases = gold_impacts(gold)
    assert list(cases) == ["b", "a"]
    assert list(cases["b"].value) == [1, 3] and list(cases["b"].index) == [0, 1]


def test_canonical_mechanism_maps_app_and_gisd_spellings():
    assert canonical_mechanism("Bio-fouling") == "Bio-fouling or other direct physical disturbance"
    assert canonical_mechanism("Transmission of diseases to native species") == "Transmission of disease"
    assert canonical_mechanism(" predation ") == "Predation"

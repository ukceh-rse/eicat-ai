from eicat_eval.eicat import CATEGORIES, CATEGORY_CODES, SEVERITY, by_severity, category_label, mechanism_label


def test_severity_orders_data_deficient_lowest():
    assert by_severity() == ["DD", "MC", "MN", "MO", "MR", "MV"]
    assert by_severity(descending=True) == ["MV", "MR", "MO", "MN", "MC", "DD"]
    assert all(SEVERITY[a] < SEVERITY[b] for a, b in zip(CATEGORIES, CATEGORIES[1:]))


def test_category_names_round_trip():
    assert CATEGORY_CODES["Minimal Concern"] == "MC"
    assert category_label("MC") == "Minimal\nConcern"
    assert category_label("DD", wrap=False) == "Data Deficient"


def test_mechanism_labels():
    assert mechanism_label("Transmission of disease") == "Disease\ntransmission"
    assert mechanism_label("Transmission of disease", wrap=False) == "Disease transmission"
    assert mechanism_label("Something new") == "Something new"

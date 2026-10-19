"""The EICAT vocabulary (IUCN EICAT guidelines v1.1): impact categories and mechanisms.

Categories are referred to by their two-letter codes throughout the evaluation. Data Deficient (DD)
is not a severity, but where a ranking is needed it sits below Minimal Concern.
"""

CATEGORIES = ("MC", "MN", "MO", "MR", "MV")  # assessed categories, least to most severe
DATA_DEFICIENT = "DD"
CATEGORY_NAMES = {  # display order used by every figure: severity, then Data Deficient
    "MC": "Minimal Concern",
    "MN": "Minor",
    "MO": "Moderate",
    "MR": "Major",
    "MV": "Massive",
    "DD": "Data Deficient",
}
CATEGORY_CODES = {name: code for code, name in CATEGORY_NAMES.items()}
SEVERITY = {"DD": 0, "MC": 1, "MN": 2, "MO": 3, "MR": 4, "MV": 5}


def by_severity(descending: bool = False) -> list[str]:
    """Every category code, Data Deficient included, ordered by `SEVERITY`."""
    return sorted(SEVERITY, key=SEVERITY.get, reverse=descending)


# Short labels for figures, keyed by the canonical GISD mechanism name (see `gisd.canonical_mechanism`).
# Covers the mechanisms that occur in the evaluation data; line breaks keep radar spokes compact.
MECHANISM_LABELS = {
    "Competition": "Competition",
    "Predation": "Predation",
    "Hybridisation": "Hybridisation",
    "Transmission of disease": "Disease\ntransmission",
    "Poisoning/toxicity": "Poisoning /\ntoxicity",
    "Grazing/herbivory/browsing": "Grazing /\nherbivory",
    "Chemical impact on ecosystem": "Chemical\nimpact",
    "Physical impact on ecosystem": "Physical\nimpact",
    "Structural impact on ecosystem": "Structural\nimpact",
    "Indirect impacts through interactions with other species": "Indirect\n(via other species)",
}


def mechanism_label(mechanism: str, wrap: bool = True) -> str:
    """Short display label for a mechanism; unknown mechanisms are returned unchanged."""
    label = MECHANISM_LABELS.get(mechanism, mechanism)
    return label if wrap else label.replace("\n", " ")


def category_label(code: str, wrap: bool = True) -> str:
    """Display name for a category code, broken after its first word when `wrap` (e.g. "Minimal\\nConcern")."""
    name = CATEGORY_NAMES[code]
    return name.replace(" ", "\n", 1) if wrap else name

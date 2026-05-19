"""Utilities for normalising raw GISD export data.

Run as a script to produce a normalised CSV:
    uv run utils/gisd.py --input data/gisd.csv --output data/gisd_clean.csv
"""
import csv
import argparse
from pathlib import Path

# Raw GISD exports contain inconsistent casing, trailing whitespace, and typos
# in the Impact mechanism field. This map canonicalises all known variants.
MECH_NORM: dict[str, str] = {
    "bio-fouling or other direct physical disturbance": "Bio-fouling or other direct physical disturbance",
    "chemical impact on ecosystem": "Chemical impact on ecosystem",
    "chemical impact on ecosystems": "Chemical impact on ecosystem",
    "competition": "Competition",
    "grazing/herbivory/browsing": "Grazing/herbivory/browsing",
    "hybridisation": "Hybridisation",
    "indirect impacts through interactions with other species": "Indirect impacts through interactions with other species",
    "interaction with other alien species": "Interaction with other alien species",
    "physical impact on ecosystem": "Physical impact on ecosystem",
    "poisoning/ toxicity": "Poisoning/toxicity",
    "poisoning/toxicity": "Poisoning/toxicity",
    "predation": "Predation",
    "structural impact on ecosystem": "Structural impact on ecosystem",
    "transmission of desease": "Transmission of disease",
    "transmission of disease": "Transmission of disease",
    "transmission of diseases to native species": "Transmission of disease",
}


def normalise_mechanism(mech: str) -> str:
    """Return the canonical form of a GISD mechanism string.

    Strips whitespace, lowercases for lookup, and falls back to the
    stripped original if no mapping exists.
    """
    return MECH_NORM.get(mech.strip().lower(), mech.strip())


def normalise_csv(input_path: Path, output_path: Path) -> None:
    """Write a copy of a GISD CSV with Impact mechanism values normalised."""
    with open(input_path) as fin, open(output_path, "w", newline="") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            row["Impact mechanism"] = normalise_mechanism(row["Impact mechanism"])
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="Raw GISD CSV path")
    parser.add_argument("--output", required=True, help="Normalised output CSV path")
    args = parser.parse_args()
    normalise_csv(Path(args.input), Path(args.output))
    print(f"Normalised CSV written to: {args.output}")


if __name__ == "__main__":
    main()

"""Filter GISD data to EICAT rows and normalise mechanism strings.

Usage:
    uv run utils/filter_clean.py
    uv run utils/filter_clean.py --input data/gisd.xlsx --output data/gisd_clean.csv
    uv run utils/filter_clean.py --include-dd   # keep Data Deficient rows
"""
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

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

VALID_CATEGORIES = {"MV", "MR", "MO", "MN", "MC", "DD"}

app = typer.Typer(add_completion=False)

DEFAULT_INPUT = Path(__file__).parent.parent / "data" / "gisd.xlsx"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "data" / "gisd_clean.csv"


def normalise_mechanism(value: object) -> object:
    if pd.isna(value) or not isinstance(value, str):
        return value
    return MECH_NORM.get(value.strip().lower(), value.strip())


@app.command()
def main(
    input: Annotated[Path, typer.Option(help="Raw GISD xlsx or csv")] = DEFAULT_INPUT,
    output: Annotated[Path, typer.Option(help="Cleaned output CSV")] = DEFAULT_OUTPUT,
    include_dd: Annotated[bool, typer.Option("--include-dd", help="Keep DD rows")] = False,
) -> None:
    """Filter GISD to EICAT rows and normalise mechanism strings."""
    df = pd.read_excel(input) if input.suffix == ".xlsx" else pd.read_csv(input)
    total_rows = len(df)

    keep_cats = VALID_CATEGORIES if include_dd else VALID_CATEGORIES - {"DD"}
    df = df[df["EICAT Category"].isin(keep_cats)].copy()

    df["Impact mechanism"] = df["Impact mechanism"].apply(normalise_mechanism)

    # Drop rows missing key fields needed for analysis
    df = df.dropna(subset=["Species", "Reference", "System", "EICAT Category", "Impact mechanism"])

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)

    cats_kept = ", ".join(sorted(keep_cats))
    typer.echo(f"Rows:       {total_rows:,} → {len(df):,}")
    typer.echo(f"Categories: {cats_kept}")
    typer.echo(f"Species:    {df['Species'].nunique():,} unique")
    typer.echo(f"References: {df['Reference'].nunique():,} unique")
    typer.echo(f"Saved:      {output}")


if __name__ == "__main__":
    app()

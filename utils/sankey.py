"""Create EICAT impact Sankey diagram and output percentage distributions.

Flow: Unique References → Unique Species → Systems → EICAT Categories → Mechanisms

Each row in the cleaned CSV represents one (species, reference, mechanism) assessment.
The Sankey is built at the (species × reference) pair level — each pair is assigned
a primary system (mode), primary category (highest severity), and primary mechanism
(most frequent) to produce one analytical unit per paper-species combination.

Usage:
    uv run utils/sankey.py
    uv run utils/sankey.py --output data/sankey.html --percentages data/percentages.json
    uv run utils/sankey.py --png data/sankey.png
"""
import json
from pathlib import Path
from typing import Annotated, Optional

import pandas as pd
import plotly
import plotly.graph_objects as go
import typer

app = typer.Typer(add_completion=False)

DEFAULT_INPUT = Path(__file__).parent.parent / "data" / "gisd_clean.csv"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "data" / "sankey.html"
DEFAULT_PERCENTAGES = Path(__file__).parent.parent / "data" / "percentages.json"

CAT_SEVERITY: dict[str, int] = {"MV": 5, "MR": 4, "MO": 3, "MN": 2, "MC": 1, "DD": 0}
CAT_LABELS: dict[str, str] = {
    "MV": "Massive",
    "MR": "Major",
    "MO": "Moderate",
    "MN": "Minor",
    "MC": "Minimal Concern",
    "DD": "Data Deficient",
}


def make_papers(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate to one row per (Species, Reference) with primary System/Category/Mechanism."""

    def primary_cat(cats: pd.Series) -> str:
        return max(cats, key=lambda c: CAT_SEVERITY.get(c, 0))

    return (
        df.groupby(["Species", "Reference"], sort=False)
        .agg(
            System=("System", lambda x: x.mode().iloc[0]),
            Category=("EICAT Category", primary_cat),
            Mechanism=("Impact mechanism", lambda x: x.mode().iloc[0]),
        )
        .reset_index()
    )


def make_species(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate to one row per unique Species with primary System/Category/Mechanism."""

    def primary_cat(cats: pd.Series) -> str:
        return max(cats, key=lambda c: CAT_SEVERITY.get(c, 0))

    return (
        df.groupby("Species", sort=False)
        .agg(
            System=("System", lambda x: x.mode().iloc[0]),
            Category=("EICAT Category", primary_cat),
            Mechanism=("Impact mechanism", lambda x: x.mode().iloc[0]),
        )
        .reset_index()
    )


def compute_percentages(papers: pd.DataFrame) -> dict:
    total = len(papers)

    joint = (
        papers.groupby(["System", "Category", "Mechanism"])
        .size()
        .div(total)
        .reset_index(name="proportion")
    )

    return {
        "total_papers": total,
        "total_references": int(papers["Reference"].nunique()),
        "total_species": int(papers["Species"].nunique()),
        "system": (papers["System"].value_counts() / total).round(6).to_dict(),
        "category": (papers["Category"].value_counts() / total).round(6).to_dict(),
        "mechanism": (papers["Mechanism"].value_counts() / total).round(6).to_dict(),
        "joint": {
            f"{r.System}|{r.Category}|{r.Mechanism}": round(r.proportion, 6)
            for r in joint.itertuples()
        },
    }


def build_sankey(papers: pd.DataFrame, species: pd.DataFrame) -> go.Figure:
    n_refs = papers["Reference"].nunique()
    n_species = len(species)

    refs_label = f"References ({n_refs:,})"
    sp_label = f"Species ({n_species:,})"

    p = papers.copy()
    p["Category"] = p["Category"].map(CAT_LABELS).fillna(p["Category"])
    sp = species.copy()

    # All flows use paper/impact counts throughout so node inflow == outflow and
    # there are no visual gaps. System node *labels* show unique species counts
    # (which have nearly identical proportions to impacts at this scale).
    species_per_system: dict[str, int] = sp.groupby("System").size().to_dict()

    e_refs_sp = pd.DataFrame([{"source": refs_label, "target": sp_label, "value": len(p)}])

    e_sp_sys = (
        p.groupby("System").size().reset_index(name="value")
        .rename(columns={"System": "target"})
        .assign(source=sp_label)
    )

    e_sys_cat = (
        p.groupby(["System", "Category"]).size().reset_index(name="value")
        .rename(columns={"System": "source", "Category": "target"})
    )

    e_cat_mech = (
        p.groupby(["Category", "Mechanism"]).size().reset_index(name="value")
        .rename(columns={"Category": "source", "Mechanism": "target"})
    )

    flows = pd.concat([e_refs_sp, e_sp_sys, e_sys_cat, e_cat_mech], ignore_index=True)

    all_labels = list(dict.fromkeys(
        [refs_label, sp_label]
        + p["System"].unique().tolist()
        + p["Category"].unique().tolist()
        + p["Mechanism"].unique().tolist()
    ))
    idx = {label: i for i, label in enumerate(all_labels)}

    node_totals: dict = {
        **flows.groupby("source")["value"].sum().to_dict(),
        **flows.groupby("target")["value"].sum().to_dict(),
    }

    palette = plotly.colors.qualitative.D3
    colors = [palette[i % len(palette)] for i in range(len(all_labels))]
    color_map = dict(zip(all_labels, colors))

    def rgba(color: str, alpha: float = 0.35) -> str:
        if color.startswith("#"):
            r, g, b = plotly.colors.hex_to_rgb(color)
        else:
            r, g, b = plotly.colors.unlabel_rgb(color)
        return f"rgba({r},{g},{b},{alpha})"

    def node_label(label: str) -> str:
        if label.startswith("References (") or label.startswith("Species ("):
            return label
        short = label[:28] + "…" if len(label) > 29 else label
        if label in species_per_system:
            return f"{short} ({species_per_system[label]} species)"
        n = node_totals.get(label, "")
        return f"{short} ({n})"

    fig = go.Figure(
        go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=[node_label(l) for l in all_labels],
                color=colors,
            ),
            link=dict(
                source=flows["source"].map(idx).tolist(),
                target=flows["target"].map(idx).tolist(),
                value=flows["value"].tolist(),
                color=[rgba(color_map[s]) for s in flows["source"]],
            ),
        )
    )

    fig.update_layout(
        title_text=f"GISD EICAT Impact Distribution  ({n_refs:,} references · {n_species:,} species)",
        font_size=12,
        height=850,
        width=1400,
    )
    return fig


@app.command()
def main(
    input: Annotated[Path, typer.Option(help="Cleaned GISD CSV")] = DEFAULT_INPUT,
    output: Annotated[Path, typer.Option(help="Sankey HTML output")] = DEFAULT_OUTPUT,
    png: Annotated[Optional[Path], typer.Option(help="Sankey PNG output (requires kaleido)")] = None,
    percentages: Annotated[Path, typer.Option(help="Percentages JSON output")] = DEFAULT_PERCENTAGES,
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Don't open browser preview")] = False,
) -> None:
    """Generate EICAT Sankey diagram and percentage distributions."""
    df = pd.read_csv(input)
    papers = make_papers(df)
    species = make_species(df)
    pct = compute_percentages(papers)

    typer.echo(f"Unique references : {pct['total_references']:,}")
    typer.echo(f"Unique species    : {pct['total_species']:,}")
    typer.echo(f"Paper-species pairs: {pct['total_papers']:,}")

    typer.echo("\nSystem distribution:")
    for k, v in sorted(pct["system"].items(), key=lambda x: -x[1]):
        typer.echo(f"  {k:<35} {v:.1%}")

    typer.echo("\nCategory distribution:")
    for k, v in sorted(pct["category"].items(), key=lambda x: -x[1]):
        typer.echo(f"  {k:<35} {v:.1%}")

    typer.echo("\nMechanism distribution:")
    for k, v in sorted(pct["mechanism"].items(), key=lambda x: -x[1]):
        typer.echo(f"  {k:<35} {v:.1%}")

    percentages.parent.mkdir(parents=True, exist_ok=True)
    percentages.write_text(json.dumps(pct, indent=2))
    typer.echo(f"\nPercentages → {percentages}")

    fig = build_sankey(papers, species)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output))
    typer.echo(f"Sankey HTML → {output}")

    if png:
        png.parent.mkdir(parents=True, exist_ok=True)
        fig.write_image(str(png))
        typer.echo(f"Sankey PNG  → {png}")

    if not no_browser:
        fig.show()


if __name__ == "__main__":
    app()

"""Create stratified batches from available papers.

Reads the researcher-marked references spreadsheet (from references.py), joins with
the cleaned GISD data, then samples and stratifies papers across N batches of M each.

Stratification uses the joint (System × Category × Mechanism) percentages from the
percentages.json produced by sankey.py.  Papers are allocated to strata proportionally
then distributed across batches with a round-robin scheme so that every batch closely
mirrors the overall distribution.

Usage:
    uv run utils/batch.py --batches 5 --size 20
    uv run utils/batch.py --batches 10 --size 15 \\
        --references data/references.xlsx \\
        --gisd data/gisd_clean.csv \\
        --percentages data/percentages.json \\
        --output-dir data/batches
"""
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Annotated, Optional

import pandas as pd
import typer
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

sys.path.insert(0, str(Path(__file__).parent))
from create_template import create_template

app = typer.Typer(add_completion=False)

TEMPLATE_COLUMNS: list[dict] = [
    {"name": "Species/Reference Text", "width": 50},
    {
        "name": "EICAT Category",
        "values": ["Massive", "Major", "Moderate", "Minor", "Minimal Concern", "Data Deficient", "No Alien Populations"],
    },
    {
        "name": "Impact mechanism",
        "values": [
            "Competition", "Predation", "Hybridisation", "Transmission of disease",
            "Parasitism", "Poisoning/toxicity", "Bio-fouling or other direct physical disturbance",
            "Grazing/herbivory/browsing", "Chemical impact on ecosystem", "Physical impact on ecosystem",
            "Structural impact on ecosystem", "Indirect impacts through interactions with other species",
        ],
    },
    {"name": "Evidence for EICAT impact category", "width": 60},
    {"name": "Confidence Rating", "values": ["low", "medium", "high"]},
    {"name": "Impacted native species"},
]

CAT_SEVERITY: dict[str, int] = {"MV": 5, "MR": 4, "MO": 3, "MN": 2, "MC": 1, "DD": 0}

DEFAULT_REFERENCES = Path(__file__).parent.parent / "data" / "references.xlsx"
DEFAULT_GISD = Path(__file__).parent.parent / "data" / "gisd_clean.csv"
DEFAULT_PERCENTAGES = Path(__file__).parent.parent / "data" / "percentages.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "batches"
DEFAULT_PAPERS_DIR = Path(__file__).parent.parent / "data" / "papers"


# ── helpers ───────────────────────────────────────────────────────────────────

def first_author_year(reference: str) -> tuple[str, str]:
    surname = re.match(r"^([A-Za-z'][A-Za-z'-]+)", reference.strip())
    year = re.search(r"\b(19|20)\d{2}\b", reference)
    return (
        surname.group(1).lower() if surname else "unknown",
        year.group() if year else "unknown",
    )



def batch_label(i: int) -> str:
    label, n = "", i + 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        label = chr(ord("a") + r) + label
    return label


# ── data loading ──────────────────────────────────────────────────────────────

def load_available_references(xlsx_path: Path) -> set[str]:
    """Return the set of reference strings marked available (Y) by the researcher."""
    from openpyxl import load_workbook
    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    ref_col = headers.index("Reference")
    avail_col = headers.index("Available")

    available = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        ref = row[ref_col]
        avail = str(row[avail_col] or "").strip().upper()
        if ref and avail == "Y":
            available.add(str(ref).strip())
    return available


def make_papers(df: pd.DataFrame, available_refs: set[str]) -> pd.DataFrame:
    """Deduplicate to one (Species, Reference) pair per row; filter to available refs."""

    def primary_cat(cats: pd.Series) -> str:
        return max(cats, key=lambda c: CAT_SEVERITY.get(c, 0))

    papers = (
        df[df["Reference"].isin(available_refs)]
        .groupby(["Species", "Reference"], sort=False)
        .agg(
            System=("System", lambda x: x.mode().iloc[0]),
            Category=("EICAT Category", primary_cat),
            Mechanism=("Impact mechanism", lambda x: x.mode().iloc[0]),
        )
        .reset_index()
    )
    papers["stratum"] = papers["System"] + "|" + papers["Category"] + "|" + papers["Mechanism"]
    return papers.reset_index(drop=True)


# ── stratified allocation ─────────────────────────────────────────────────────

def allocate(papers: pd.DataFrame, total: int, joint_pct: dict[str, float], seed: int) -> pd.DataFrame:
    """Sample papers proportionally to joint strata targets; fill remainder from unmatched pool."""
    target_counts = {s: round(p * total) for s, p in joint_pct.items()}

    # Adjust largest stratum so allocations sum exactly to total
    alloc_sum = sum(target_counts.values())
    if alloc_sum != total:
        largest = max(target_counts, key=target_counts.get)
        target_counts[largest] += total - alloc_sum

    selected_parts: list[pd.DataFrame] = []
    for stratum, target_n in target_counts.items():
        if target_n <= 0:
            continue
        pool = papers[papers["stratum"] == stratum]
        if pool.empty:
            continue
        n = min(target_n, len(pool))
        selected_parts.append(pool.sample(n, random_state=seed))

    if not selected_parts:
        return pd.DataFrame(columns=papers.columns)

    selected = pd.concat(selected_parts, ignore_index=True)

    # Fill any shortfall with papers from unrepresented strata
    shortfall = total - len(selected)
    if shortfall > 0:
        used_idx = set(selected.index)
        remaining = papers[~papers.index.isin(used_idx)]
        if not remaining.empty:
            extra = remaining.sample(min(shortfall, len(remaining)), random_state=seed)
            selected = pd.concat([selected, extra], ignore_index=True)

    return selected


def assign_to_batches(selected: pd.DataFrame, n_batches: int) -> list[pd.DataFrame]:
    """Round-robin assignment within each stratum, then trim batches to equal size."""
    selected = selected.copy()
    selected["_batch"] = -1

    for stratum, group in selected.groupby("stratum", sort=False):
        for i, idx in enumerate(group.index):
            selected.at[idx, "_batch"] = i % n_batches

    batches: list[pd.DataFrame] = []
    target_size = len(selected) // n_batches

    for b in range(n_batches):
        batch = selected[selected["_batch"] == b].drop(columns=["stratum", "_batch"])
        batches.append(batch.reset_index(drop=True))

    # Balance: move excess rows from over-size batches to under-size ones
    sizes = [len(b) for b in batches]
    for _ in range(1000):
        max_b = sizes.index(max(sizes))
        min_b = sizes.index(min(sizes))
        if sizes[max_b] - sizes[min_b] <= 1:
            break
        # Move last row of the over-full batch to the under-full batch
        row = batches[max_b].iloc[[-1]]
        batches[max_b] = batches[max_b].iloc[:-1]
        batches[min_b] = pd.concat([batches[min_b], row], ignore_index=True)
        sizes = [len(b) for b in batches]

    return batches


# ── xlsx output ───────────────────────────────────────────────────────────────

def write_batch_xlsx(path: Path, batch: pd.DataFrame, label: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = f"Batch {label.upper()}"

    headers = ["#", "Species", "Reference", "PDF Filename"]
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="366092")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for rank, row in enumerate(batch.itertuples(), start=1):
        author, year = first_author_year(row.Reference)
        pdf = f"{author}_{year}.pdf"

        r = ws.max_row + 1
        ws.cell(r, 1, rank).alignment = Alignment(horizontal="center")
        ws.cell(r, 2, row.Species).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(r, 3, row.Reference).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(r, 4, pdf).alignment = Alignment(vertical="top")

    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 70
    ws.column_dimensions["D"].width = 25
    ws.freeze_panes = "A2"

    wb.save(path)


def copy_papers(batch: pd.DataFrame, batch_dir: Path, papers_dir: Path) -> tuple[int, int]:
    """Copy available PDFs into the batch folder. Returns (copied, missing) counts."""
    copied = missing = 0
    seen: set[str] = set()
    for row in batch.itertuples():
        author, year = first_author_year(row.Reference)
        pdf = f"{author}_{year}.pdf"
        if pdf in seen:
            continue
        seen.add(pdf)
        src = papers_dir / pdf
        if src.exists():
            shutil.copy2(src, batch_dir / pdf)
            copied += 1
        else:
            missing += 1
    return copied, missing


def write_batch_template(path: Path, batch: pd.DataFrame, label: str) -> None:
    entries = [f"{row.Species} / {row.Reference}" for row in batch.itertuples()]
    cols = [TEMPLATE_COLUMNS[0] | {"values": entries}] + TEMPLATE_COLUMNS[1:]
    create_template(cols, str(path))


# ── distribution report ───────────────────────────────────────────────────────

def distribution_report(batches: list[pd.DataFrame], joint_pct: dict[str, float]) -> None:
    all_papers = pd.concat(batches, ignore_index=True)
    total = len(all_papers)

    actual_joint = (
        all_papers.groupby(["System", "Category", "Mechanism"])
        .size()
        .div(total)
        .reset_index(name="actual")
    )

    typer.echo("\nDistribution vs. target (joint strata, top 15 by target):")
    typer.echo(f"  {'Stratum':<45} {'Target':>8} {'Actual':>8} {'Diff':>8}")
    typer.echo("  " + "-" * 73)

    for stratum, target in sorted(joint_pct.items(), key=lambda x: -x[1])[:15]:
        sys_, cat, mech = stratum.split("|")
        row = actual_joint[
            (actual_joint["System"] == sys_) &
            (actual_joint["Category"] == cat) &
            (actual_joint["Mechanism"] == mech)
        ]
        actual = row["actual"].iloc[0] if not row.empty else 0.0
        diff = actual - target
        label = f"{sys_}/{cat}/{mech[:20]}"
        typer.echo(f"  {label:<45} {target:>7.1%}  {actual:>7.1%}  {diff:>+7.1%}")

    typer.echo(f"\nBatch sizes: {[len(b) for b in batches]}")


# ── main ──────────────────────────────────────────────────────────────────────

@app.command()
def main(
    batches: Annotated[int, typer.Option("--batches", help="Number of batches to create")],
    size: Annotated[int, typer.Option("--size", help="Papers per batch")],
    references: Annotated[Path, typer.Option(help="References xlsx (with Available column marked)")] = DEFAULT_REFERENCES,
    gisd: Annotated[Path, typer.Option(help="Cleaned GISD CSV")] = DEFAULT_GISD,
    percentages: Annotated[Path, typer.Option(help="Percentages JSON from sankey.py")] = DEFAULT_PERCENTAGES,
    output_dir: Annotated[Path, typer.Option(help="Directory for output batch xlsx files")] = DEFAULT_OUTPUT_DIR,
    papers_dir: Annotated[Path, typer.Option(help="Directory containing paper PDFs to copy")] = DEFAULT_PAPERS_DIR,
    seed: Annotated[Optional[int], typer.Option(help="Random seed for reproducibility")] = None,
) -> None:
    """Create stratified batches from researcher-marked available papers."""
    pct_data = json.loads(percentages.read_text())
    joint_pct: dict[str, float] = pct_data["joint"]

    df = pd.read_csv(gisd)
    available_refs = load_available_references(references)
    typer.echo(f"Available references: {len(available_refs):,}")

    papers = make_papers(df, available_refs)
    typer.echo(f"Paper-species pairs:  {len(papers):,}  ({papers['Reference'].nunique():,} refs, {papers['Species'].nunique():,} species)")

    total_needed = batches * size
    if len(papers) < total_needed:
        typer.echo(
            f"Warning: only {len(papers):,} pairs available; requested {total_needed:,} ({batches} × {size})",
            err=True,
        )

    selected = allocate(papers, min(total_needed, len(papers)), joint_pct, seed or 42)
    batch_list = assign_to_batches(selected, batches)

    output_dir.mkdir(parents=True, exist_ok=True)
    for i, batch_df in enumerate(batch_list):
        label = batch_label(i)
        batch_dir = output_dir / f"batch_{label}"
        batch_dir.mkdir(exist_ok=True)
        write_batch_xlsx(batch_dir / f"batch_{label}.xlsx", batch_df, label)
        write_batch_template(batch_dir / f"batch_{label}_template.xlsx", batch_df, label)
        copied, missing = copy_papers(batch_df, batch_dir, papers_dir)
        typer.echo(f"  batch_{label}/  ({len(batch_df)} papers, {copied} PDFs copied, {missing} missing)")

    distribution_report(batch_list, joint_pct)
    typer.echo(f"\nBatches saved to: {output_dir}")


if __name__ == "__main__":
    app()

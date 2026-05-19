"""Generate stratified candidate papers from GISD for EICAT evaluation batches.

Assumes the GISD CSV has already been normalised (see gisd.py).

Sample candidates to an xlsx (clickable Scholar links) or stdout (CSV):
    uv run utils/sample_batch.py sample --gisd data/gisd_clean.csv --output candidates.xlsx
    uv run utils/sample_batch.py sample --gisd data/gisd_clean.csv > candidates.csv

Generate an annotator xlsx after marking available=Y / length_ok=Y in the candidates file:
    uv run utils/sample_batch.py generate candidates.xlsx --output batch1.xlsx
"""
import csv
import json
import random
import sys
import urllib.parse
from pathlib import Path
from typing import Annotated, Optional

import typer
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

sys.path.insert(0, str(Path(__file__).parent))
from create_template import create_template

app = typer.Typer()

GISD_CSV = Path(__file__).parent.parent / "data" / "gisd.csv"

CAT_SEVERITY: dict[str, int] = {"MV": 5, "MR": 4, "MO": 3, "MN": 2, "MC": 1, "DD": 0}

DEFAULT_TARGET_SYSTEM: dict[str, float] = {"Terrestrial": 0.68, "Freshwater_terrestrial": 0.32}
DEFAULT_TARGET_CATEGORY: dict[str, float] = {"MC": 0.31, "MN": 0.42, "MO": 0.18, "MR": 0.06, "MV": 0.01}
DEFAULT_TARGET_MECH_NAMED: dict[str, float] = {
    "Competition": 0.35,
    "Predation": 0.29,
    "Grazing/herbivory/browsing": 0.09,
    "Hybridisation": 0.08,
}

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

CSV_FIELDS = ["rank", "species", "reference", "system", "category", "mechanism", "scholar_url", "available", "length_ok", "notes"]


def batch_label(i: int) -> str:
    """Convert a 0-based index to an alphabetic label: 0→'a', 25→'z', 26→'aa', etc."""
    label, n = "", i + 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        label = chr(ord("a") + r) + label
    return label


def write_batch(file, candidates: list[dict], start_rank: int = 1) -> None:
    """Write candidates as CSV to an open file object (stdout fallback)."""
    writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for i, p in enumerate(candidates, start=start_rank):
        writer.writerow({**p, "rank": i, "scholar_url": scholar_url(p["reference"]), "available": "", "length_ok": "", "notes": ""})


_LINK_FONT = Font(color="0563C1", underline="single")


def write_batch_xlsx(path: Path, candidates: list[dict], start_rank: int = 1) -> None:
    """Write candidates as xlsx with clickable Scholar hyperlinks."""
    wb = Workbook()
    ws = wb.active
    ws.append(CSV_FIELDS)
    for i, p in enumerate(candidates, start=start_rank):
        url = scholar_url(p["reference"])
        ws.append([i, p["species"], p["reference"], p["system"], p["category"], p["mechanism"], url, "", "", ""])
        cell = ws.cell(row=ws.max_row, column=CSV_FIELDS.index("scholar_url") + 1)
        cell.hyperlink = url
        cell.value = "Scholar"
        cell.font = _LINK_FONT
    wb.save(path)


def scholar_url(reference: str) -> str:
    """Build a Google Scholar search URL for a reference string."""
    return f"https://scholar.google.com/scholar?q={urllib.parse.quote_plus(reference)}"


def load_papers(path: Path, target_systems: dict[str, float]) -> list[dict]:
    """Group GISD rows into one entry per (species, reference) pair.

    Filters to rows whose system is in target_systems and excludes DD-only
    papers. Assigns primary category (highest severity) and primary mechanism
    (most frequent) per pair to support stratified sampling.
    """
    groups: dict[tuple, dict] = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            species = row["Species"].strip()
            ref = row["Reference"].strip()
            system = row["System"].strip()
            cat = row["EICAT Category"].strip()
            mech = row["Impact mechanism"].strip()

            if not ref or not species or system not in target_systems or not cat or cat == "DD":
                continue

            key = (species, ref)
            if key not in groups:
                groups[key] = {"species": species, "reference": ref, "system": system, "cats": [], "mechs": []}
            groups[key]["cats"].append(cat)
            groups[key]["mechs"].append(mech)

    papers = []
    for g in groups.values():
        primary_cat = max(g["cats"], key=lambda c: CAT_SEVERITY.get(c, 0))
        mech_counts: dict[str, int] = {}
        for m in g["mechs"]:
            mech_counts[m] = mech_counts.get(m, 0) + 1
        papers.append({
            "species": g["species"],
            "reference": g["reference"],
            "system": g["system"],
            "category": primary_cat,
            "mechanism": max(mech_counts, key=mech_counts.__getitem__),
        })
    return papers


def paper_weight(
    paper: dict,
    target_system: dict[str, float],
    target_category: dict[str, float],
    target_mech_named: dict[str, float],
    remaining_mech_weight: float,
) -> float:
    """Compute a sampling weight as the product of the paper's three target proportions.

    Papers whose system, category, or mechanism fall outside the target distributions
    receive a weight of zero and will never be selected.
    """
    mech_w = target_mech_named.get(paper["mechanism"], remaining_mech_weight)
    return target_system.get(paper["system"], 0) * target_category.get(paper["category"], 0) * mech_w


def sample_candidates(
    path: Path,
    n: int = 15,
    seed: int | None = None,
    target_system: dict[str, float] = DEFAULT_TARGET_SYSTEM,
    target_category: dict[str, float] = DEFAULT_TARGET_CATEGORY,
    target_mech_named: dict[str, float] = DEFAULT_TARGET_MECH_NAMED,
    max_per_mechanism: int | None = None,
) -> list[dict]:
    """Weighted random sample of (species, reference) pairs without replacement.

    Each paper is weighted by the product of its system, category, and mechanism
    proportions so the batch approximately reflects the target distributions.
    Unnamed mechanisms share the remaining proportion equally.

    max_per_mechanism caps how many papers of any single mechanism can be selected,
    preventing competition/predation from flooding the batch. Defaults to n // 3.
    Pass 0 to disable the cap.
    """
    papers = load_papers(path, target_system)
    if seed is not None:
        random.seed(seed)

    all_mechs = {p["mechanism"] for p in papers}
    unnamed = [m for m in all_mechs if m not in target_mech_named]
    remaining_mech_w = (1 - sum(target_mech_named.values())) / len(unnamed) if unnamed else 0

    cap = max_per_mechanism if max_per_mechanism is not None else max(2, n // 3)
    pool = [(paper_weight(p, target_system, target_category, target_mech_named, remaining_mech_w), p) for p in papers]
    mech_seen: dict[str, int] = {}
    selected = []
    while len(selected) < n:
        eligible = [i for i, (w, p) in enumerate(pool) if cap == 0 or mech_seen.get(p["mechanism"], 0) < cap]
        if not eligible:
            break
        total = sum(pool[i][0] for i in eligible)
        if total == 0:
            break
        r, cumsum = random.uniform(0, total), 0.0
        for idx in eligible:
            cumsum += pool[idx][0]
            if cumsum >= r:
                p = pool[idx][1]
                selected.append(p)
                mech_seen[p["mechanism"]] = mech_seen.get(p["mechanism"], 0) + 1
                pool.pop(idx)
                break

    return selected


def _first_author_year(reference: str) -> tuple[str, str]:
    import re
    surname = re.match(r"^([A-Za-z'][A-Za-z'-]*)", reference.strip())
    surname = surname.group(1).lower() if surname else "unknown"
    year = re.search(r"\b(19|20)\d{2}\b", reference)
    year = year.group() if year else "unknown"
    return surname, year


def _pdf_filename(reference: str, papers_dir: Path | None) -> str:
    """Return the PDF filename for a paper, checking the papers dir for actual files."""
    author, year = _first_author_year(reference)
    stem = f"{author}_{year}"
    if papers_dir and papers_dir.exists():
        matches = sorted(papers_dir.glob(f"{stem}*.pdf"))
        if matches:
            return matches[0].name
    return f"{stem}.pdf"


def _read_batch_papers(input_path: Path) -> list[dict]:
    papers = []
    if input_path.suffix == ".xlsx":
        wb = load_workbook(input_path)
        ws = wb.active
        headers = [c.value for c in ws[1]]
        for row in ws.iter_rows(min_row=2, values_only=True):
            d = dict(zip(headers, row))
            if d.get("species") and d.get("reference"):
                papers.append(d)
    else:
        with open(input_path) as f:
            for row in csv.DictReader(f):
                if row.get("species") and row.get("reference"):
                    papers.append(row)
    return papers


def generate_xlsx(input_path: Path, output: Path) -> None:
    """Read a batch xlsx (or CSV) and produce an annotator xlsx template.

    All rows in the file are included — assumes the batch has already been
    curated to contain only available papers.
    """
    papers = _read_batch_papers(input_path)
    entries = [f"{p['species']} / {p['reference']}" for p in papers]
    cols = [TEMPLATE_COLUMNS[0] | {"values": entries}] + TEMPLATE_COLUMNS[1:]
    create_template(cols, str(output))


def generate_participant_csv(input_path: Path, output: Path, papers_dir: Path | None = None) -> None:
    """Write a participant CSV with species, reference, and pdf filename only.

    Omits impact category, mechanism, and system so participants go in blind.
    """
    papers = _read_batch_papers(input_path)
    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["species", "reference", "pdf"])
        writer.writeheader()
        for p in papers:
            writer.writerow({
                "species": p["species"],
                "reference": p["reference"],
                "pdf": _pdf_filename(p["reference"], papers_dir),
            })


@app.command()
def sample(
    gisd: Annotated[Path, typer.Option(help="Normalised GISD CSV path")] = GISD_CSV,
    output: Annotated[Optional[Path], typer.Option(help="Output CSV path for a single batch (default: stdout)")] = None,
    output_dir: Annotated[Path, typer.Option(help="Directory to write batch files when --batches > 1 (default: cwd)")] = Path("."),
    batches: Annotated[int, typer.Option(help="Number of non-overlapping batches to generate")] = 1,
    count: Annotated[int, typer.Option(help="Number of candidates per batch")] = 15,
    seed: Annotated[Optional[int], typer.Option(help="Random seed for reproducibility")] = None,
    target_system: Annotated[Optional[str], typer.Option(help="System proportions override as JSON")] = None,
    target_category: Annotated[Optional[str], typer.Option(help="EICAT category proportions override as JSON")] = None,
    target_mechanism: Annotated[Optional[str], typer.Option(help="Named mechanism proportions override as JSON")] = None,
    max_per_mechanism: Annotated[Optional[int], typer.Option(help="Max papers per mechanism per batch (0=unlimited, default: count//3)")] = None,
) -> None:
    """Sample stratified candidate papers from GISD into one or more non-overlapping batch CSVs."""
    sys_ = json.loads(target_system) if target_system else DEFAULT_TARGET_SYSTEM
    cat = json.loads(target_category) if target_category else DEFAULT_TARGET_CATEGORY
    mech = json.loads(target_mechanism) if target_mechanism else DEFAULT_TARGET_MECH_NAMED

    all_candidates = sample_candidates(gisd, count * batches, seed, sys_, cat, mech, max_per_mechanism)
    if len(all_candidates) < count * batches:
        typer.echo(f"Warning: only {len(all_candidates)} candidates available for {batches} × {count}", err=True)

    groups = [all_candidates[i * count : (i + 1) * count] for i in range(batches)]

    if batches == 1:
        if output:
            write_batch_xlsx(output, groups[0])
        else:
            write_batch(sys.stdout, groups[0])
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        for i, group in enumerate(groups):
            path = output_dir / f"batch_{batch_label(i)}.xlsx"
            write_batch_xlsx(path, group)
            typer.echo(f"Written: {path}")


@app.command()
def generate(
    batch: Annotated[Path, typer.Argument(help="Curated batch xlsx (or CSV)")],
    output: Annotated[Path, typer.Option(help="Output annotator xlsx path")] = Path("batch.xlsx"),
) -> None:
    """Generate an annotator xlsx template from a curated batch file."""
    generate_xlsx(batch, output)


@app.command()
def generate_all(
    batches_dir: Annotated[Path, typer.Option(help="Directory containing curated batch xlsx files")] = Path("batches"),
    output_dir: Annotated[Path, typer.Option(help="Directory to write annotator xlsx and participant CSV files")] = Path("annotators"),
    papers_dir: Annotated[Path, typer.Option(help="Root directory containing downloaded PDFs (papers/batch_X/ subfolders)")] = Path("../papers"),
) -> None:
    """Generate annotator templates and participant CSVs for all batches in a directory."""
    xlsx_files = sorted(batches_dir.glob("batch_*.xlsx"))
    if not xlsx_files:
        typer.echo(f"No batch_*.xlsx files found in {batches_dir}", err=True)
        raise typer.Exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    for xlsx in xlsx_files:
        name = xlsx.stem
        label = name.replace("batch_", "Batch_")
        generate_xlsx(xlsx, output_dir / f"{label}_template.xlsx")
        generate_participant_csv(xlsx, output_dir / f"{label}.csv", papers_dir / name)
        typer.echo(f"{name}: {label}_template.xlsx + {label}.csv written")


if __name__ == "__main__":
    app()

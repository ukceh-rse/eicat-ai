"""Annotator spreadsheets for the inter-annotator agreement (IAA) study.

Input is a directory with one `.xlsx` or `.csv` file per annotator (`paths.IAA_INPUT`), one row per
impact. The paper is named in the first row of its block only, so it is forward-filled.

Anonymity: a file's stem (the annotator's initials) is replaced by a stable pseudonym (A1, A2, ...)
before anything else happens. The mapping lives in `annotators.json`, gitignored and the only place
initials are written down; it grows additively, so an id never changes once assigned.

Exclusions: annotators in `EXCLUDED` are dropped as their sheets are read, so they never reach any
metric, figure or report.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from eicat_eval.eicat import CATEGORIES, CATEGORY_CODES, CATEGORY_NAMES
from eicat_eval.paths import ANNOTATOR_EXPERIENCE, ANNOTATOR_IDS

# A7: an outlier, overlapping with almost no other annotator on which impacts are present.
EXCLUDED = frozenset({"A7"})

PAPER_COL = "Species/Reference Text"
EVIDENCE_COL = "Evidence for EICAT impact category"
CATEGORY_COL = "EICAT Category"
MECHANISM_COL = "Impact mechanism"
RANK = {CATEGORY_NAMES[c]: i for i, c in enumerate(CATEGORIES)}  # category name -> 0 (MC) ... 4 (MV)


# ── anonymity ─────────────────────────────────────────────────────────────────


def anonymize(stems: set[str], mapping_path: Path = ANNOTATOR_IDS) -> dict[str, str]:
    """Pseudonym for each file stem, assigning the next free id to stems not seen before."""
    mapping = json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    for stem in sorted(stems - mapping.keys()):
        mapping[stem] = f"A{len(mapping) + 1}"
    mapping_path.write_text(json.dumps(mapping, indent=2))
    return {stem: mapping[stem] for stem in stems}


def deanonymize(mapping_path: Path = ANNOTATOR_IDS) -> dict[str, str]:
    """Id -> real initials, for the local named-output figures only. Never feed this into a report."""
    mapping = json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    return {anon_id: stem for stem, anon_id in mapping.items()}


def sort_ids(ids) -> list[str]:
    """Sort anonymous ids numerically (A2 before A10), not lexicographically."""
    return sorted(ids, key=lambda a: int(a[1:]))


def annotator_ids(input_dir: Path) -> list[str]:
    """Pseudonyms of every annotator file in `input_dir`, excluded annotators included."""
    return sort_ids(anonymize({f.stem for f in sheet_files(input_dir)}).values())


# ── reading sheets ────────────────────────────────────────────────────────────


def sheet_files(input_dir: Path) -> list[Path]:
    return sorted(list(input_dir.glob("*.xlsx")) + list(input_dir.glob("*.csv")))


def paper_key(paper) -> str:
    """Key a paper on its species prefix: some annotators omit the " / reference" suffix."""
    return str(paper).split(" / ")[0].strip()


def read_sheets(input_dir: Path, *columns: str) -> Iterator[tuple[Path, str, pd.DataFrame]]:
    """(file, pseudonym, rows) per included annotator; rows hold the forward-filled paper and `columns`."""
    files = sheet_files(input_dir)
    ids = anonymize({f.stem for f in files})
    for f in files:
        if ids[f.stem] in EXCLUDED:
            continue
        read = pd.read_csv if f.suffix == ".csv" else pd.read_excel
        rows = read(f, usecols=[PAPER_COL, *columns])
        rows[PAPER_COL] = rows[PAPER_COL].ffill()
        yield f, ids[f.stem], rows


def load_evidence(input_dir: Path) -> pd.DataFrame:
    """One row per evidence quote: annotator, paper, quote_id (`<annotator>-<n>`) and evidence text."""
    records = []
    for _, annotator, rows in read_sheets(input_dir, EVIDENCE_COL):
        rows = rows.dropna(subset=[EVIDENCE_COL])
        for i, (paper, evidence) in enumerate(zip(rows[PAPER_COL], rows[EVIDENCE_COL])):
            records.append({"annotator": annotator, "paper": paper_key(paper), "quote_id": f"{annotator}-{i}",
                            "evidence": str(evidence).strip()})
    return pd.DataFrame(records)


def load_labels(input_dir: Path) -> pd.DataFrame:
    """One row per evidence quote: quote_id (as in `load_evidence`), category code and mechanisms.

    `category` is a code ("MN", "DD") or None; `mechanisms` is a frozenset of names, since some annotators
    give two ("Competition / Predation") or number them ("(1) Competition").
    """
    records = []
    for _, annotator, rows in read_sheets(input_dir, EVIDENCE_COL, CATEGORY_COL, MECHANISM_COL):
        rows = rows.dropna(subset=[EVIDENCE_COL])
        for i, (category, mechanism) in enumerate(zip(rows[CATEGORY_COL], rows[MECHANISM_COL])):
            category = CATEGORY_CODES.get(str(category).split(" - ")[-1].strip()) if pd.notna(category) else None
            mechanisms = frozenset() if pd.isna(mechanism) else frozenset(
                re.sub(r"^\(\d+\)\s*", "", m).strip().replace(" on the ecosystem", " on ecosystem")
                for m in str(mechanism).split(" / "))
            records.append({"quote_id": f"{annotator}-{i}", "category": category, "mechanisms": mechanisms})
    return pd.DataFrame(records)


def load_categories(input_dir: Path) -> pd.DataFrame:
    """One row per rated impact: annotator, paper and category name (e.g. "Minor", "Data Deficient").

    Values written as "MC - Minimal Concern" are normalised; anything still unrecognised is reported
    and skipped rather than silently dropped.
    """
    records = []
    for f, annotator, rows in read_sheets(input_dir, CATEGORY_COL):
        for paper, value in zip(rows[PAPER_COL], rows[CATEGORY_COL]):
            if pd.isna(paper) or pd.isna(value):
                continue
            category = str(value).split(" - ")[-1].strip()
            if category not in CATEGORY_CODES:
                print(f"NOTE: {f.name} has an unrecognised EICAT Category value {value!r}, excluding it from the ranking.")
                continue
            records.append({"annotator": annotator, "paper": paper_key(paper), "category": category})
    return pd.DataFrame(records)


def coverage(evidence: pd.DataFrame) -> dict[str, set[str]]:
    """Paper -> annotators who annotated it, from `load_evidence` output."""
    return {paper: set(group) for paper, group in evidence.groupby("paper").annotator}


def max_category_matrix(categories: pd.DataFrame) -> pd.DataFrame:
    """Papers x annotators; cell = rank (`RANK`) of the most severe category given, nan if none.

    Data Deficient rows carry no severity, so they are left out of the ranking.
    """
    ranked = categories.assign(rank=categories.category.map(RANK)).dropna(subset=["rank"])
    return ranked.groupby(["paper", "annotator"])["rank"].max().unstack("annotator")


# ── alignments and groups ─────────────────────────────────────────────────────


def drop_annotators(clusters: pd.DataFrame, excluded=EXCLUDED) -> pd.DataFrame:
    """Remove annotators from an impact alignment (`align_impacts.py` output), and impacts only they found."""
    kept = clusters.annotators.str.split(",").apply(lambda ids: [a for a in ids if a not in excluded])
    quotes = clusters.quote_ids.str.split(",").apply(lambda ids: [q for q in ids if q.rsplit("-", 1)[0] not in excluded])
    clusters = clusters.assign(annotators=kept.str.join(","), n_annotators=kept.str.len(), quote_ids=quotes.str.join(","))
    return clusters[clusters.n_annotators > 0].reset_index(drop=True)


def load_experience(path: Path = ANNOTATOR_EXPERIENCE) -> dict[str, str]:
    """Anonymous id -> "Skilled" / "Unskilled" EICAT experience, excluded annotators left out.

    Taken from the "EICAT experience level" column of the Task 4.4 participation form.
    """
    return {a: level for a, level in json.loads(path.read_text()).items() if a not in EXCLUDED}

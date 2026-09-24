"""Align EICAT impacts across annotators by evidence quote.

A baseline for inter-annotator agreement: ignoring EICAT category/mechanism labels,
do annotators pick out the *same underlying impacts* from a paper? Annotators phrase
and split impacts differently, so quotes are clustered semantically by an LLM rather
than matched as strings. Run: `uv run --project eval eval/align_impacts.py --input eval-data/batch_a`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from itertools import combinations
from pathlib import Path

import krippendorff
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelSettings
from statsmodels.stats.inter_rater import fleiss_kappa

from anonymize import anonymize, sort_ids

PAPER_COL = "Species/Reference Text"
EVIDENCE_COL = "Evidence for EICAT impact category"
DEFAULT_MODEL = "bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0"

SYSTEM_PROMPT = """You align EICAT impact assessments made by different annotators on the same paper.
Each annotator selected evidence quotes supporting an impact; every quote is tagged [annotator-index].
Group quotes that describe the SAME underlying ecological impact into one cluster.

Rules:
- Judge only by the impact described in the evidence text; ignore any EICAT category or mechanism wording.
- Every quote id must appear in at least one cluster.
- A cluster may contain several quotes from the same annotator, if that annotator split one impact across rows.
- Assign a quote to more than one cluster only if it genuinely describes multiple distinct impacts.
- Do not merge genuinely distinct impacts just because they concern the same species."""


class Cluster(BaseModel):
    summary: str = Field(description="Short description of the shared underlying impact.")
    quote_ids: list[str] = Field(description="Ids of all quotes describing this one impact.")


class Alignment(BaseModel):
    clusters: list[Cluster]


def load(input_dir: Path) -> pd.DataFrame:
    files = sorted(list(input_dir.glob("*.xlsx")) + list(input_dir.glob("*.csv")))
    ids = anonymize({f.stem for f in files})

    rows = []
    for f in files:
        annotator = ids[f.stem]
        read = pd.read_csv if f.suffix == ".csv" else pd.read_excel
        df = read(f, usecols=[PAPER_COL, EVIDENCE_COL])
        df[PAPER_COL] = df[PAPER_COL].ffill()
        df = df.dropna(subset=[EVIDENCE_COL])
        for i, (paper, ev) in enumerate(zip(df[PAPER_COL], df[EVIDENCE_COL])):
            rows.append(
                {
                    "annotator": annotator,
                    # key on the species prefix: some annotators omit the "/ reference" suffix
                    "paper": str(paper).split(" / ")[0].strip(),
                    "quote_id": f"{annotator}-{i}",
                    "evidence": str(ev).strip(),
                }
            )
    return pd.DataFrame(rows)


async def align_paper(agent: Agent[None, Alignment], paper: str, group: pd.DataFrame) -> Alignment:
    quotes = "\n".join(f"[{r.quote_id}] {r.evidence}" for r in group.itertuples())
    result = await agent.run(f"Paper: {paper}\n\nQuotes:\n{quotes}")
    return result.output


async def run(input_dir: Path, model: str) -> tuple[pd.DataFrame, dict[str, set[str]]]:
    data = load(input_dir)
    coverage = {p: set(a) for p, a in data.groupby("paper").annotator}
    annotator_of = dict(zip(data.quote_id, data.annotator))
    agent = Agent(
        model,
        output_type=Alignment,
        system_prompt=SYSTEM_PROMPT,
        model_settings=ModelSettings(temperature=0.0, max_tokens=4000),
    )

    records = []
    for paper, group in data.groupby("paper"):
        alignment = await align_paper(agent, paper, group)
        assigned = [q for c in alignment.clusters for q in c.quote_ids]
        missing = set(group.quote_id) - set(assigned)
        unknown = set(assigned) - set(group.quote_id)
        multi = {q for q in assigned if assigned.count(q) > 1}
        if missing or unknown:
            print(f"  ! {paper[:50]}: unassigned={missing or '-'} unknown={unknown or '-'}")
        if multi:
            print(f"  · {paper[:50]}: quotes spanning multiple impacts: {sorted(multi)}")
        for c in alignment.clusters:
            present = sort_ids({annotator_of[q] for q in c.quote_ids if q in annotator_of})
            records.append(
                {
                    "paper": paper,
                    "summary": c.summary,
                    "n_annotators": len(present),
                    "annotators": ",".join(present),
                    "quote_ids": ",".join(c.quote_ids),
                }
            )
    return pd.DataFrame(records), coverage


def presence_matrix(clusters: pd.DataFrame, coverage: dict[str, set[str]], annotators: list[str]) -> np.ndarray:
    """Impacts (rows) x annotators (cols): 1=identified, 0=annotated paper but missed it, nan=did not annotate."""
    found = clusters.annotators.str.split(",").apply(set)
    rows = [
        [1.0 if a in found.iloc[i] else (0.0 if a in coverage[clusters.paper.iloc[i]] else np.nan) for a in annotators]
        for i in range(len(clusters))
    ]
    return np.array(rows)


def report(clusters: pd.DataFrame, coverage: dict[str, set[str]], metrics_path: Path) -> None:
    annotators = sort_ids({a for row in clusters.annotators for a in row.split(",")})
    found = clusters.annotators.str.split(",").apply(set)

    pairwise = []
    for a, b in combinations(annotators, 2):
        scores = []
        for paper, g in clusters.groupby("paper"):
            if not {a, b} <= coverage[paper]:
                continue
            fa = {i for i in g.index if a in found[i]}
            fb = {i for i in g.index if b in found[i]}
            if fa | fb:
                scores.append(len(fa & fb) / len(fa | fb))
        mean = sum(scores) / len(scores) if scores else float("nan")
        pairwise.append({"pair": f"{a}-{b}", "jaccard": mean, "n_shared_papers": len(scores)})

    valid = [p for p in pairwise if not np.isnan(p["jaccard"])]
    vals = np.array([p["jaccard"] for p in valid])
    best, worst = max(valid, key=lambda p: p["jaccard"]), min(valid, key=lambda p: p["jaccard"])
    jaccard_summary = {
        "n_pairs": len(valid),
        "mean": float(vals.mean()),
        "median": float(np.median(vals)),
        "std": float(vals.std(ddof=1)) if len(vals) > 1 else 0.0,
        "min": {"pair": worst["pair"], "jaccard": worst["jaccard"]},
        "max": {"pair": best["pair"], "jaccard": best["jaccard"]},
    }

    matrix = presence_matrix(clusters, coverage, annotators)
    complete = not np.isnan(matrix).any()
    metrics = {
        "n_impacts": len(clusters),
        "n_papers": int(clusters.paper.nunique()),
        "annotators": annotators,
        "jaccard_summary": jaccard_summary,
        "krippendorff_alpha": float(krippendorff.alpha(reliability_data=matrix.T, level_of_measurement="nominal")),
        "fleiss_kappa": float(fleiss_kappa(np.column_stack([(matrix == 0).sum(1), (matrix == 1).sum(1)]))) if complete else None,
        "agreement_distribution": {int(k): int(v) for k, v in clusters.n_annotators.value_counts().sort_index().items()},
        "pairwise_jaccard": pairwise,
        "per_paper": [
            {"paper": p, "n_impacts": len(g), "unanimous": int((g.n_annotators == len(coverage[p])).sum())}
            for p, g in clusters.groupby("paper")
        ],
    }
    metrics_path.write_text(json.dumps(metrics, indent=2))

    s = jaccard_summary
    print(f"\n{len(clusters)} distinct impacts across {metrics['n_papers']} papers, {len(annotators)} annotators")
    print(f"Pairwise Jaccard over {s['n_pairs']} pairs: mean {s['mean']:.2f}, median {s['median']:.2f}, sd {s['std']:.2f}")
    print(f"  best  {s['max']['jaccard']:.2f} ({s['max']['pair']})")
    print(f"  worst {s['min']['jaccard']:.2f} ({s['min']['pair']})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=Path("eval-data/batch_a"))
    ap.add_argument("--output", type=Path, default=Path("eval/iaa_alignment.csv"))
    ap.add_argument("--metrics", type=Path, default=Path("eval/iaa_metrics.json"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    clusters, coverage = asyncio.run(run(args.input, args.model))
    clusters.to_csv(args.output, index=False)
    report(clusters, coverage, args.metrics)
    print(f"\nWrote {len(clusters)} clusters to {args.output}; full metrics to {args.metrics}")


if __name__ == "__main__":
    main()

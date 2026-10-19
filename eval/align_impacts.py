"""Align EICAT impacts across annotators by evidence quote.

A baseline for inter-annotator agreement: ignoring EICAT category/mechanism labels,
do annotators pick out the *same underlying impacts* from a paper? Annotators phrase
and split impacts differently, so quotes are clustered semantically by an LLM rather
than matched as strings.

    uv run --project eval eval/align_impacts.py            # cluster with Bedrock, then score
    uv run --project eval eval/align_impacts.py --reuse    # re-score existing clusters, no model calls
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelSettings
from statsmodels.stats.inter_rater import fleiss_kappa

from eicat_eval.agreement import krippendorff_alpha, pairwise_jaccard, presence_matrix
from eicat_eval.annotators import coverage as paper_coverage, drop_annotators, load_evidence, sort_ids
from eicat_eval.paths import IAA_ALIGNMENT, IAA_INPUT, IAA_METRICS

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


async def align_paper(agent: Agent[None, Alignment], paper: str, group: pd.DataFrame) -> Alignment:
    quotes = "\n".join(f"[{r.quote_id}] {r.evidence}" for r in group.itertuples())
    result = await agent.run(f"Paper: {paper}\n\nQuotes:\n{quotes}")
    return result.output


async def run(input_dir: Path, model: str) -> tuple[pd.DataFrame, dict[str, set[str]]]:
    data = load_evidence(input_dir)
    coverage = paper_coverage(data)
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


def report(clusters: pd.DataFrame, coverage: dict[str, set[str]], metrics_path: Path) -> None:
    annotators = sort_ids({a for row in clusters.annotators for a in row.split(",")})
    pairwise = [{"pair": f"{a}-{b}", "jaccard": mean, "n_shared_papers": n}
                for (a, b), (mean, n) in pairwise_jaccard(clusters, coverage, annotators).items()]

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
        "krippendorff_alpha": krippendorff_alpha(matrix, "nominal"),
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
    ap.add_argument("--input", type=Path, default=IAA_INPUT, help="Directory of annotator spreadsheets.")
    ap.add_argument("--output", type=Path, default=IAA_ALIGNMENT)
    ap.add_argument("--metrics", type=Path, default=IAA_METRICS)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--reuse", action="store_true",
                    help="Recompute metrics from the existing --output clusters (no model calls), dropping excluded annotators.")
    args = ap.parse_args()

    if args.reuse:
        clusters = drop_annotators(pd.read_csv(args.output))
        coverage = paper_coverage(load_evidence(args.input))
    else:
        clusters, coverage = asyncio.run(run(args.input, args.model))
    clusters.to_csv(args.output, index=False)
    report(clusters, coverage, args.metrics)
    print(f"\nWrote {len(clusters)} clusters to {args.output}; full metrics to {args.metrics}")


if __name__ == "__main__":
    main()

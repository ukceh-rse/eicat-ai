"""Compare scored GISD evaluation runs of different extraction models: accuracy and cost.

Each run directory must have been through `gisd_eval.py run` (or extract -> judge -> score) on the
same papers. Token usage comes from the `usage` the API records per analysis; prices are rough
on-demand Bedrock list prices (USD per million tokens) looked up when this was written, so
re-check them before relying on the cost figures.

    uv run --project eval eval/gisd_compare.py eval/runs/cmp_* --out eval/runs/model_comparison.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# (input, output) USD per million tokens, matched by substring of the model id, with an optional
# long-prompt tier (prompt tokens above which the whole request is billed at the second rate).
# Anthropic and OpenAI models on Bedrock add 10% on regional (eu./us.) endpoints over global ones.
PRICES = {
    "claude-haiku-5-5": ((0.10 * 1.1, 0.50 * 1.1), (100_000, (0.50 * 1.1, 2.50 * 1.1))),  # eu. regional
    "claude-sonnet-5-5": ((2.00 * 1.1, 10.00 * 1.1), None),  # eu. regional
    "openai.gpt-5.5": ((5.00, 30.00), (272_000, (10.00, 45.00))),  # global; AWS card: $5.50/$33 in-region
    "nova-pro": ((0.80, 3.20), None),
    "nova-lite": ((0.06, 0.24), None),
}


def price(model: str) -> tuple[tuple[float, float], tuple | None] | None:
    return next((p for k, p in PRICES.items() if k in model), None)


def record_cost(usage: dict, p: tuple[tuple[float, float], tuple | None]) -> float:
    """Cost of one analysis; its prompt size per request (usually one) picks the price tier."""
    (rate_in, rate_out), long = p
    tokens_in, tokens_out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    if long and tokens_in / max(usage.get("requests", 1), 1) > long[0]:
        rate_in, rate_out = long[1]
    return (tokens_in * rate_in + tokens_out * rate_out) / 1e6


def f1_ci(run: Path, n: int = 5000) -> tuple[float, float]:
    """95% bootstrap interval for micro F1, resampling cases."""
    c = pd.read_csv(run / "cases.csv")
    idx = np.random.default_rng(0).integers(0, len(c), (n, len(c)))
    tp, fp, fn = (c[k].to_numpy()[idx].sum(axis=1) for k in ("tp", "fp", "fn"))
    f1 = np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros(n), where=tp > 0)
    return float(np.percentile(f1, 2.5)), float(np.percentile(f1, 97.5))


def summarise(run: Path) -> dict:
    m = json.loads((run / "metrics.json").read_text())
    records = [json.loads(p.read_text()) for p in sorted((run / "extracted").glob("*.json"))]
    model = next((r["model"] for r in records if r.get("model")), "unknown")
    tokens_in = sum(r.get("usage", {}).get("input_tokens", 0) for r in records)
    tokens_out = sum(r.get("usage", {}).get("output_tokens", 0) for r in records)
    requests = sum(r.get("usage", {}).get("requests", 0) for r in records)
    p = price(model)
    cost = sum(record_cost(r.get("usage", {}), p) for r in records) if p else None
    det, cat, mech = m["detection"]["micro"], m["labels"]["category"]["matched"], m["labels"]["mechanism"]["matched"]
    return {
        "run": run.name,
        "model": model.removeprefix("bedrock:"),
        "cases": m["n_cases_scored"],
        "failed": m["n_cases_failed"],
        "extracted": m["n_extracted_impacts"],
        "tp": det["tp"],
        "precision": det["precision"],
        "recall": det["recall"],
        "f1": det["f1"],
        "f1_ci": f1_ci(run),
        "macro_f1": m["detection"]["macro"]["f1"],
        "category_acc": cat["micro"]["f1"] if "micro" in cat else None,
        "mechanism_acc": mech["micro"]["f1"] if "micro" in mech else None,
        "max_cat_acc": m["max_category"]["exact_accuracy"],
        "max_cat_mad": m["max_category"]["mean_abs_distance"],
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "requests": requests,
        "price_in": p[0][0] if p else None,
        "price_out": p[0][1] if p else None,
        "cost": cost,
    }


def fmt(v, spec: str = ".2f") -> str:
    return "-" if v is None else format(v, spec)


def render(rows: list[dict]) -> str:
    gold = rows[0]["tp"] / rows[0]["recall"] if rows and rows[0]["recall"] else None
    out = ["# Extraction model comparison on GISD", ""]
    out += [f"Runs: {len(rows)}. Same sampled papers in every run" + (f"; {gold:.0f} GISD impacts." if gold else "."), ""]
    out += ["## Accuracy", "",
            "| Model | Cases (failed) | Extracted | TP | Precision | Recall | F1 | F1 95% CI | Macro F1 | Category acc. | Mechanism acc. | Max-category acc. | Max-cat. MAD |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in rows:
        out.append(
            f"| {r['model']} | {r['cases']} ({r['failed']}) | {r['extracted']} | {r['tp']} | {fmt(r['precision'])} | {fmt(r['recall'])} "
            f"| **{fmt(r['f1'])}** | {fmt(r['f1_ci'][0])}-{fmt(r['f1_ci'][1])} | {fmt(r['macro_f1'])} | {fmt(r['category_acc'])} | {fmt(r['mechanism_acc'])} | {fmt(r['max_cat_acc'])} | {fmt(r['max_cat_mad'])} |"
        )
    out += ["", "F1 is micro detection F1; its interval is a 95% bootstrap over cases. Category and mechanism accuracy are",
            "over judged pairs only (was the label right, given the impact was found).", ""]
    out += ["## Cost", "",
            "| Model | $/M input | $/M output | Input tokens | Output tokens | Requests | Run cost ($) | $ per paper | $ per TP impact | F1 per $ |",
            "|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in rows:
        per_paper = r["cost"] / (r["cases"] + r["failed"]) if r["cost"] is not None and r["cases"] + r["failed"] else None
        per_tp = r["cost"] / r["tp"] if r["cost"] is not None and r["tp"] else None
        f1_per_dollar = r["f1"] / r["cost"] if r["cost"] else None
        out.append(
            f"| {r['model']} | {fmt(r['price_in'])} | {fmt(r['price_out'])} | {r['tokens_in']:,} | {r['tokens_out']:,} | {r['requests']} "
            f"| {fmt(r['cost'], '.4f')} | {fmt(per_paper, '.4f')} | {fmt(per_tp, '.4f')} | {fmt(f1_per_dollar, '.1f')} |"
        )
    out += ["", "Prices are rough on-demand Bedrock list prices (USD), base tier shown; requests over a model's long-prompt",
            "threshold (Haiku 5.5: 100K, GPT-5.5: 272K) are costed at its higher rate. Extraction only; the shared judge is excluded.", ""]
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", type=Path, nargs="+", help="Scored run directories.")
    parser.add_argument("--out", type=Path, help="Write the markdown report here as well as printing it.")
    args = parser.parse_args()
    rows = [summarise(r) for r in args.runs if (r / "metrics.json").exists()]
    text = render(rows)
    print(text)
    if args.out:
        args.out.write_text(text)
        (args.out.with_suffix(".json")).write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()

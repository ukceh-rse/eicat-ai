"""Score a judged GISD run: impact detection, per-class label metrics and maximum category.

Reads `gold.csv`, `extracted/` and `judged/` from a run directory (no model calls) and writes
`metrics.json`, `cases.csv`, `pairs.csv` and `impacts.csv` back into it.

1. Detection - a judged pair is a true positive, an unpaired extracted impact a false positive and
   an unpaired GISD impact a false negative. Precision/recall/F1/F2, micro (pooled) and macro (mean
   over cases).
2. Per-class label metrics for EICAT category and mechanism, in two views:
   - `matched`: classification accuracy on judged pairs only (was the label right, given the impact
     was found?);
   - `detection`: over all impacts, an impact counts towards a class only if it was paired *and*
     both sides gave it that label, so missed and spurious impacts count against their class.
   Each view gives per-class P/R/F1/F2 with support, a micro and a macro (mean over classes) average,
   and a confusion matrix (matched view; rows GISD, columns extracted).
3. Maximum category per case - the most severe GISD category vs the most severe extracted one:
   exact accuracy, mean absolute distance in category steps, and a confusion matrix.

Categories are ranked MV > MR > MO > MN > MC > DD throughout.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import fmean

import pandas as pd

from eicat_eval.eicat import SEVERITY, by_severity
from eicat_eval.gisd import canonical_mechanism, gold_impacts

CATEGORIES = by_severity(descending=True)  # MV ... DD, the label order of every category table
NONE = "none"  # max category of a case where the app extracted nothing


def max_category(categories) -> str:
    known = [c for c in categories if c in SEVERITY]
    return max(known, key=SEVERITY.get) if known else NONE


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f = lambda beta: (1 + beta**2) * precision * recall / (beta**2 * precision + recall) if precision + recall else 0.0  # noqa: E731
    return {"precision": precision, "recall": recall, "f1": f(1), "f2": f(2)}


def mean_of(rows: list[dict], keys=("precision", "recall", "f1", "f2")) -> dict[str, float | None]:
    return {k: fmean(r[k] for r in rows) if rows else None for k in keys}


def confusion(gold: list[str], predicted: list[str], labels: list[str]) -> dict:
    counts = Counter(zip(gold, predicted))
    return {"labels": labels, "matrix": [[counts[(g, p)] for p in labels] for g in labels]}


def label_metrics(gold: list[str], predicted: list[str], correct: list[str], order: list[str]) -> dict:
    """Per-class and averaged P/R/F1/F2 from the gold labels, predicted labels and correctly-labelled items.

    The populations decide the view: judged pairs only (matched), or every impact (detection).
    """
    g, p, c = Counter(gold), Counter(predicted), Counter(correct)
    classes = [k for k in order if g[k] or p[k]]
    per_class = {k: {"support": g[k], "tp": c[k], "fp": p[k] - c[k], "fn": g[k] - c[k], **prf(c[k], p[k] - c[k], g[k] - c[k])} for k in classes}
    tp, fp, fn = len(correct), len(predicted) - len(correct), len(gold) - len(correct)
    return {"per_class": per_class, "micro": {"tp": tp, "fp": fp, "fn": fn, **prf(tp, fp, fn)}, "macro": mean_of(list(per_class.values()))}


def load_cases(run_dir: Path) -> tuple[list[dict], list[dict]]:
    """Gold impacts, extracted impacts and judged pairs per case, plus cases that cannot be scored."""
    gold = gold_impacts(pd.read_csv(run_dir / "gold.csv"))
    cases, failures = [], []
    for case_id, g in gold.items():
        extracted, judged = run_dir / "extracted" / f"{case_id}.json", run_dir / "judged" / f"{case_id}.json"
        record = json.loads(extracted.read_text()) if extracted.exists() else None
        if record is None or record["status"] != "completed":
            failures.append({"case_id": case_id, "error": record["error"] if record else "not extracted"})
            continue
        if not judged.exists():
            failures.append({"case_id": case_id, "error": "not judged"})
            continue
        cases.append({
            "case_id": case_id, "pdf": record["pdf"], "species": record["species"],
            "gold": [{"category": r["EICAT Category"], "mechanism": canonical_mechanism(r["Impact mechanism"]),
                      "evidence": r["Evidence for EICAT impact category"]} for _, r in g.iterrows()],
            "extracted": [{**i, "mechanism": canonical_mechanism(i["mechanism"])} for i in record["impacts"]],
            "pairs": json.loads(judged.read_text())["pairs"],
        })  # fmt: skip
    return cases, failures


def score(run_dir: Path) -> dict:
    cases, failures = load_cases(run_dir)

    case_rows, pair_rows, impact_rows = [], [], []
    for case in cases:
        gold, ext, pairs = case["gold"], case["extracted"], case["pairs"]
        paired_ext = {p["extracted"]: p["gold"] for p in pairs}
        for p in pairs:
            g, e = gold[p["gold"]], ext[p["extracted"]]
            pair_rows.append({
                "case_id": case["case_id"], "gold_index": p["gold"], "extracted_index": p["extracted"],
                "gold_category": g["category"], "extracted_category": e["category"],
                "gold_mechanism": g["mechanism"], "extracted_mechanism": e["mechanism"],
                "reason": p["reason"], "gold_evidence": g["evidence"], "extracted_evidence": e["evidence"],
            })  # fmt: skip
        impact_rows += [
            {"case_id": case["case_id"], "extracted_index": i, "matched_gold_index": paired_ext.get(i), **imp,
             "impacted_species": "; ".join(imp["impacted_species"])}
            for i, imp in enumerate(ext)
        ]  # fmt: skip

        tp = len(pairs)
        gold_max, ext_max = max_category(g["category"] for g in gold), max_category(e["category"] for e in ext)
        case_rows.append({
            "case_id": case["case_id"], "pdf": case["pdf"], "species": case["species"],
            "n_gold": len(gold), "n_extracted": len(ext), "tp": tp, "fp": len(ext) - tp, "fn": len(gold) - tp,
            **prf(tp, len(ext) - tp, len(gold) - tp),
            "gold_max_category": gold_max, "extracted_max_category": ext_max, "max_category_exact": gold_max == ext_max,
            "max_category_distance": abs(SEVERITY[gold_max] - SEVERITY[ext_max]) if ext_max != NONE else None,
        })  # fmt: skip

    tp, fp, fn = (sum(r[k] for r in case_rows) for k in ("tp", "fp", "fn"))
    metrics = {
        "n_cases_scored": len(case_rows),
        "n_cases_failed": len(failures),
        "n_gold_impacts": tp + fn,
        "n_extracted_impacts": tp + fp,
        "judge_model": next((json.loads(p.read_text())["model"] for p in (run_dir / "judged").glob("*.json")), None),
        "detection": {"micro": {"tp": tp, "fp": fp, "fn": fn, **prf(tp, fp, fn)}, "macro": mean_of(case_rows)},
        "labels": {field: field_metrics(field, cases, pair_rows) for field in ("category", "mechanism")},
        "max_category": max_category_metrics(case_rows),
        "failures": failures,
    }

    pd.DataFrame(case_rows).to_csv(run_dir / "cases.csv", index=False)
    pd.DataFrame(pair_rows).to_csv(run_dir / "pairs.csv", index=False)
    pd.DataFrame(impact_rows).to_csv(run_dir / "impacts.csv", index=False)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print_summary(metrics, run_dir)
    return metrics


def field_metrics(field: str, cases: list[dict], pair_rows: list[dict]) -> dict:
    gold_all = [g[field] for c in cases for g in c["gold"]]
    ext_all = [e[field] for c in cases for e in c["extracted"]]
    gold_paired = [r[f"gold_{field}"] for r in pair_rows]
    ext_paired = [r[f"extracted_{field}"] for r in pair_rows]
    correct = [g for g, e in zip(gold_paired, ext_paired) if g == e]
    order = CATEGORIES if field == "category" else sorted(set(gold_all) | set(ext_all))
    return {
        "matched": {**label_metrics(gold_paired, ext_paired, correct, order),
                    "confusion": confusion(gold_paired, ext_paired, [k for k in order if k in set(gold_paired) | set(ext_paired)])},
        "detection": label_metrics(gold_all, ext_all, correct, order),
    }  # fmt: skip


def max_category_metrics(case_rows: list[dict]) -> dict:
    gold = [r["gold_max_category"] for r in case_rows]
    ext = [r["extracted_max_category"] for r in case_rows]
    distances = [r["max_category_distance"] for r in case_rows if r["max_category_distance"] is not None]
    labels = [c for c in [*CATEGORIES, NONE] if c in set(gold) | set(ext)]
    return {
        "n": len(case_rows),
        "exact_accuracy": fmean(r["max_category_exact"] for r in case_rows) if case_rows else None,
        "n_over": sum(e != NONE and SEVERITY[e] > SEVERITY[g] for g, e in zip(gold, ext)),
        "n_under": sum(e == NONE or SEVERITY[e] < SEVERITY[g] for g, e in zip(gold, ext)),
        "n_no_extraction": ext.count(NONE),
        "mean_abs_distance": fmean(distances) if distances else None,
        "confusion": confusion(gold, ext, labels),
    }


def fmt(v) -> str:
    return "-" if v is None else f"{v:.3f}"


def print_summary(m: dict, run_dir: Path) -> None:
    print(f"\nScored {m['n_cases_scored']} cases ({m['n_cases_failed']} failed/not run): "
          f"{m['n_gold_impacts']} GISD vs {m['n_extracted_impacts']} extracted impacts")  # fmt: skip
    print("                         P      R      F1     F2")
    for name, block in (("Detection micro", m["detection"]["micro"]), ("Detection macro", m["detection"]["macro"])):
        print(f"{name:<22} " + "  ".join(fmt(block[k]) for k in ("precision", "recall", "f1", "f2")))
    for field, views in m["labels"].items():
        for view, block in views.items():
            print(f"{field.title()} {view:<9} micro F1 {fmt(block['micro']['f1'])}  macro F1 {fmt(block['macro']['f1'])}")
    mc = m["max_category"]
    print(f"Max category: exact {fmt(mc['exact_accuracy'])} (n={mc['n']}), over {mc['n_over']}, under {mc['n_under']}, "
          f"mean |distance| {fmt(mc['mean_abs_distance'])}")  # fmt: skip
    for f in m["failures"]:
        print(f"  ! {f['case_id']}: {f['error']}")
    print(f"Results written to {run_dir}")

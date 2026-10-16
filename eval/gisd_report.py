"""Write `<run>/report.md` and `<run>/figures/*.png` from a scored run's `metrics.json`.

Pure matplotlib over the metrics file; no model calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from gisd_score import fmt

BLUE, ORANGE = "#2a78d6", "#eb6834"  # categorical slots 1-2 of the dataviz reference palette
INK, MUTED = "#0b0b0b", "#52514e"
METRICS = {"precision": "P", "recall": "R", "f1": "F1", "f2": "F2"}  # metric -> column abbreviation


# ── figures ───────────────────────────────────────────────────────────────────


def plot_confusion(confusion: dict, title: str, output: Path) -> None:
    labels, matrix = confusion["labels"], np.array(confusion["matrix"])
    rows = matrix.sum(axis=1, keepdims=True)
    share = np.divide(matrix, rows, out=np.zeros_like(matrix, dtype=float), where=rows > 0)  # colour by row share

    size = max(4.5, 0.6 * len(labels) + 2.5)
    fig, ax = plt.subplots(figsize=(size, size * 0.9))
    im = ax.imshow(share, cmap="Blues", vmin=0, vmax=1)
    short = [label if len(label) <= 22 else label[:20] + "…" for label in labels]
    ax.set_xticks(range(len(labels)), short, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)), short, fontsize=8)
    for i in range(len(labels)):
        for j in range(len(labels)):
            if matrix[i, j]:
                ax.text(j, i, matrix[i, j], ha="center", va="center", fontsize=8, color="white" if share[i, j] > 0.6 else INK)
    ax.set_xlabel("Extracted")
    ax.set_ylabel("GISD")
    ax.set_title(title, fontsize=10)
    fig.colorbar(im, ax=ax, label="Share of GISD row", fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def plot_per_class_f1(views: dict, title: str, output: Path) -> None:
    """Per-class F1 for the matched and detection views side by side, one bar group per class."""
    classes = list(views["detection"]["per_class"])
    y = np.arange(len(classes))
    fig, ax = plt.subplots(figsize=(7, 0.45 * len(classes) + 1.5))
    for offset, (view, colour) in zip((-0.2, 0.2), (("matched", BLUE), ("detection", ORANGE))):
        f1 = [views[view]["per_class"].get(c, {}).get("f1", 0.0) for c in classes]
        ax.barh(y + offset, f1, height=0.36, color=colour, label=view)
    support = [views["detection"]["per_class"][c]["support"] for c in classes]
    ax.set_yticks(y, [f"{c}  (n={n})" for c, n in zip(classes, support)], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("F1")
    ax.set_title(title, fontsize=10)
    ax.grid(axis="x", color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower right", fontsize=8, frameon=False, labelcolor=MUTED)
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


# ── markdown ──────────────────────────────────────────────────────────────────


def table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] + ["---:"] * (len(header) - 1)) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def scores(block: dict) -> list[str]:
    return [fmt(block[k]) for k in METRICS]


def confusion_table(confusion: dict) -> str:
    labels = confusion["labels"]
    return table(["GISD \\ extracted", *labels], [[g, *row] for g, row in zip(labels, confusion["matrix"])])


def label_section(field: str, views: dict, figures: dict[str, str]) -> str:
    detection = views["detection"]["per_class"]
    matched = views["matched"]["per_class"]
    rows = [
        [c, d["support"], *(scores(matched[c]) if c in matched else ["-"] * 4), *scores(d)]
        for c, d in detection.items()
    ]
    averages = [
        [f"**{avg}**", "", *scores(views["matched"][avg]), *scores(views["detection"][avg])] for avg in ("micro", "macro")
    ]
    header = ["Class", "GISD n", *(f"matched {a}" for a in METRICS.values()), *(f"detection {a}" for a in METRICS.values())]
    return "\n\n".join([
        f"### {field.title()}",
        table(header, rows + averages),
        f"Matched-pair confusion matrix (rows GISD, columns extracted; {sum(map(sum, views['matched']['confusion']['matrix']))} pairs):",
        confusion_table(views["matched"]["confusion"]),
        f"![{field} confusion]({figures['confusion']})\n\n![{field} per-class F1]({figures['f1']})",
    ])  # fmt: skip


def write_report(m: dict, run_dir: Path, figures: dict) -> Path:
    det, mc = m["detection"], m["max_category"]
    sections = [
        f"# GISD evaluation report — `{run_dir.name}`",
        (f"{m['n_cases_scored']} cases scored ({m['n_cases_failed']} failed or not run): "
        f"{m['n_gold_impacts']} GISD impacts vs {m['n_extracted_impacts']} extracted. "
        f"Impacts paired by LLM judge `{m['judge_model']}`."),
        "## 1. Impact detection",
        ("A judged pair is a true positive, an unpaired extracted impact a false positive, an unpaired GISD impact a "
        "false negative. Micro pools counts over all cases; macro averages the per-case scores."),
        table(["", "TP", "FP", "FN", "Precision", "Recall", "F1", "F2"], [
            ["Micro", det["micro"]["tp"], det["micro"]["fp"], det["micro"]["fn"], *scores(det["micro"])],
            ["Macro", "", "", "", *scores(det["macro"])],
        ]),
        "## 2. EICAT labels per class",
        ("**matched**: label accuracy on judged pairs only (given the impact was found, was its label right?). "
        "**detection**: over all impacts; an impact counts for a class only if it was paired and both sides gave it "
        "that label, so missed and spurious impacts count against their class. Micro pools all impacts (for "
        "matched it equals accuracy); macro is the unweighted mean over classes."),
        *(label_section(field, views, figures[field]) for field, views in m["labels"].items()),
        "## 3. Maximum EICAT category per case",
        ("Most severe GISD category vs most severe extracted category (MV > MR > MO > MN > MC > DD; `none` = no impacts "
        "extracted)."),
        table(["Cases", "Exact accuracy", "Over-estimated", "Under-estimated", "No extraction", "Mean abs distance"],
              [[mc["n"], fmt(mc["exact_accuracy"]), mc["n_over"], mc["n_under"], mc["n_no_extraction"], fmt(mc["mean_abs_distance"])]]),
        confusion_table(mc["confusion"]),
        f"![max category confusion]({figures['max_category']})",
    ]  # fmt: skip
    if m["failures"]:
        sections += ["## Failed or unscored cases", table(["Case", "Error"], [[f["case_id"], f["error"]] for f in m["failures"]])]
    path = run_dir / "report.md"
    path.write_text("\n\n".join(sections) + "\n")
    return path


def report(run_dir: Path) -> Path:
    m = json.loads((run_dir / "metrics.json").read_text())
    fig_dir = run_dir / "figures"
    fig_dir.mkdir(exist_ok=True)

    figures = {}
    for field, views in m["labels"].items():
        figures[field] = {"confusion": f"figures/{field}_confusion.png", "f1": f"figures/{field}_f1.png"}
        if views["matched"]["confusion"]["labels"]:
            plot_confusion(views["matched"]["confusion"], f"{field.title()} on matched impacts", run_dir / figures[field]["confusion"])
        if views["detection"]["per_class"]:
            plot_per_class_f1(views, f"{field.title()} F1 per class", run_dir / figures[field]["f1"])
    figures["max_category"] = "figures/max_category_confusion.png"
    if m["max_category"]["confusion"]["labels"]:
        plot_confusion(m["max_category"]["confusion"], "Maximum category per case", run_dir / figures["max_category"])

    path = write_report(m, run_dir, figures)
    print(f"Report written to {path}")
    return path

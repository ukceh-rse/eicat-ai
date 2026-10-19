"""Context figures for the EICAT-AI talk, in OneSTOP brand style: the EICAT scale, what GISD holds,
and diagrams of the app pipeline and the GISD evaluation.

    uv run --project eval eval/present_context.py [--bare] [--out DIR]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, PathPatch, Rectangle
from matplotlib.path import Path as MplPath

from eicat_eval import style
from eicat_eval.eicat import CATEGORY_NAMES, MECHANISM_LABELS, mechanism_label
from eicat_eval.gisd import read_gisd
from eicat_eval.paths import EVAL
from eicat_eval.style import DARK, GREEN, INK, LIGHT, MID, MUTED, RAMP, SURFACE

DEFINITIONS = {  # EICAT guidelines v1.1, Box 1, shortened
    "MC": "Negligible impacts;\nno reduction in native\nindividuals' performance",
    "MN": "Reduces performance\nof native individuals;\nno population decline",
    "MO": "Declines in population\nsize of at least one\nnative taxon",
    "MR": "Local population\nextinction; naturally\nreversible",
    "MV": "Irreversible local or\nglobal extinction of a\nnative taxon",
}


def canvas(title: str, subtitle: str):
    fig, ax = style.slide(title, subtitle)
    fig.subplots_adjust(left=0.03, right=0.97, top=0.8, bottom=0.04)
    ax.set_axis_off()
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 7)
    return fig, ax


def box(ax, x, y, w, h, title, body="", fill=LIGHT, text=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.18", facecolor=fill,
                                edgecolor="none"))
    if body:
        ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", fontsize=16, fontfamily=style.HEADING,
                fontweight="bold", color=text)
        ax.text(x + w / 2, y + h * 0.3, body, ha="center", va="center", fontsize=11.5, color=text, linespacing=1.4)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=16, fontfamily=style.HEADING,
                fontweight="bold", color=text)


def arrow(ax, start, end, colour=MUTED, style_="-|>", **kwargs):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle=style_, mutation_scale=22, linewidth=2.2, color=colour,
                                 shrinkA=4, shrinkB=4, **kwargs))


# ── 1. the EICAT scale ────────────────────────────────────────────────────────


def fig_scale(out: Path) -> None:
    fig, ax = canvas("EICAT: five severity categories, twelve mechanisms",
                     "IUCN standard for classifying the environmental impacts of alien taxa (EICAT guidelines v1.1).")
    w, gap, y = 2.75, 0.2, 2.6
    for i, (abbr, definition) in enumerate(DEFINITIONS.items()):
        name = CATEGORY_NAMES[abbr]
        x = 0.35 + i * (w + gap)
        dark = i >= 2
        ax.add_patch(FancyBboxPatch((x, y), w, 2.6, boxstyle="round,pad=0,rounding_size=0.18", facecolor=RAMP[i],
                                    edgecolor="none"))
        colour = SURFACE if dark else DARK
        ax.text(x + w / 2, y + 1.85, abbr, ha="center", va="center", fontsize=38, fontfamily=style.HEADING,
                fontweight="bold", color=colour)
        ax.text(x + w / 2, y + 0.85, name, ha="center", va="center", fontsize=17, fontfamily=style.HEADING,
                fontweight="bold", color=colour)
        ax.text(x + w / 2, y - 0.85, definition, ha="center", va="center", fontsize=12, color=INK, linespacing=1.4)
    arrow(ax, (0.6, 5.75), (15.2, 5.75), colour=DARK)
    ax.text(7.9, 6.15, "Increasing severity of impact on native biota", ha="center", fontsize=14, color=DARK,
            fontfamily=style.HEADING, fontweight="bold")
    ax.text(0.35, 0.25, "+ Data Deficient (DD): too little evidence to classify.   "
                        "A species is scored by its most severe impact across all mechanisms.",
            fontsize=12.5, color=MUTED)
    style.save(fig, out / "eicat_scale.png")


# ── 2. what GISD holds ────────────────────────────────────────────────────────


def fig_gisd(out: Path) -> None:
    data = read_gisd()
    categories = data["EICAT Category"].value_counts()
    mechanisms = data["Impact mechanism"].str.split(";").explode().str.strip().value_counts()
    mechanisms = mechanisms[mechanisms.index.isin(MECHANISM_LABELS)]
    fig, (left, right) = style.slide(
        f"GISD: {len(data):,} EICAT impact records, {data.Species.nunique()} species, "
        f"{data.Reference.nunique()} references",
        "The gold standard for evaluation: GISD EICAT export, one row per assessed impact.",
        ncols=2, gridspec_kw={"width_ratios": [1, 1.5]})
    fig.subplots_adjust(left=0.07, right=0.97, top=0.74, bottom=0.12, wspace=0.55)

    order = ["DD", *[c for c in ("MC", "MN", "MO", "MR", "MV")]]
    values = [categories.get(c, 0) for c in order]
    colours = ["#C9CFCB", "#C8EACF", *RAMP[1:]]  # DD neutral grey; MC one step darker than the page tint
    left.bar(range(len(order)), values, 0.68, color=colours, zorder=2)
    for i, v in enumerate(values):
        left.text(i, v + max(values) * 0.02, f"{v}", ha="center", va="bottom", fontsize=12.5, color=INK)
    left.set_xticks(range(len(order)), order, fontsize=14, color=INK, fontfamily=style.HEADING, fontweight="bold")
    left.set_title("By EICAT category", fontsize=16, fontfamily=style.HEADING, fontweight="bold", color=DARK,
                   loc="left", pad=14)
    left.grid(axis="x", visible=False)
    left.spines["left"].set_visible(False)

    names = [mechanism_label(m, wrap=False) for m in mechanisms.index][::-1]
    right.barh(range(len(names)), mechanisms.values[::-1], 0.66, color=MID, zorder=2)
    for i, v in enumerate(mechanisms.values[::-1]):
        right.text(v + mechanisms.max() * 0.01, i, f"{v}", va="center", fontsize=11.5, color=INK)
    right.set_yticks(range(len(names)), names, fontsize=12, color=INK)
    right.set_title("By impact mechanism", fontsize=16, fontfamily=style.HEADING, fontweight="bold", color=DARK,
                    loc="left", pad=14)
    right.grid(axis="y", visible=False)
    right.spines["left"].set_visible(False)
    style.save(fig, out / "gisd_profile.png")


# ── 2b. GISD as a Sankey ──────────────────────────────────────────────────────

SYSTEMS = {"Terrestrial": "Terrestrial", "Freshwater_terrestrial": "Freshwater & terrestrial",
           "Freshwater": "Freshwater"}
CATEGORY_COLOUR = {"MC": "#C8EACF", "MN": RAMP[1], "MO": RAMP[2], "MR": RAMP[3], "MV": RAMP[4], "DD": "#B9C2BD"}
OTHER_BELOW = 10  # mechanisms with fewer records fold into "Other"
RARE_NAMES = {"Bio-fouling or other direct physical disturbance": "bio-fouling",
              "Physical impact on ecosystem": "physical impact",
              "Interaction with other alien species": "interaction with other aliens"}


def ribbon(ax, x0, y0, x1, y1, height, colour, alpha):
    """A band of constant height from (x0, y0) to (x1, y1); y is the band's top edge."""
    mid = (x0 + x1) / 2
    verts = [(x0, y0), (mid, y0), (mid, y1), (x1, y1), (x1, y1 - height),
             (mid, y1 - height), (mid, y0 - height), (x0, y0 - height), (x0, y0)]
    codes = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4, MplPath.LINETO,
             MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4, MplPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MplPath(verts, codes), facecolor=colour, edgecolor="none", alpha=alpha, zorder=1))


def fig_gisd_sankey(out: Path) -> None:
    data = read_gisd()
    counts = data["Impact mechanism"].value_counts()
    rare = counts[counts < OTHER_BELOW].index
    data["mechanism"] = data["Impact mechanism"].where(~data["Impact mechanism"].isin(rare), "Other")
    data["system"] = data.System.map(SYSTEMS)
    data["category"] = data["EICAT Category"]
    total = len(data)
    data["records"] = f"{total:,} impact records"

    mechanisms = [m for m in data.mechanism.value_counts().index if m != "Other"] + ["Other"]
    columns = [  # (column field, node order)
        ("records", [f"{total:,} impact records"]),
        ("system", [s for s in SYSTEMS.values() if s in set(data.system)]),
        ("category", ["MC", "MN", "MO", "MR", "MV", "DD"]),
        ("mechanism", mechanisms),
    ]
    xs = [0.0, 0.3, 0.6, 0.9]
    bar, gap = 0.012, 0.032
    scale = min((1 - gap * (len(nodes) - 1)) / total for _, nodes in columns)

    # node tops, top-down, each column centred vertically
    top, size = {}, {}
    for (field, nodes), x in zip(columns, xs):
        sizes = data[field].value_counts()
        height = sum(sizes[n] for n in nodes) * scale + gap * (len(nodes) - 1)
        y = 0.5 + height / 2
        for node in nodes:
            top[(field, node)], size[(field, node)] = y, sizes[node]
            y -= sizes[node] * scale + gap

    other = ", ".join(RARE_NAMES.get(m, m.lower()) for m in rare)
    fig, ax = style.slide(f"GISD: {total:,} EICAT impact records by system, severity and mechanism",
                          f"Band width = number of impact records; colour = EICAT category. Other: {other}.")
    fig.subplots_adjust(left=0.03, right=0.93, top=0.8, bottom=0.06)
    ax.set_axis_off()
    ax.set_xlim(-0.2, 1.17)
    ax.set_ylim(-0.02, 1.08)

    out_offset = {key: 0.0 for key in top}
    in_offset = {key: 0.0 for key in top}
    for c in range(len(columns) - 1):
        (src_field, src_nodes), (dst_field, dst_nodes) = columns[c], columns[c + 1]
        flows = data.groupby([src_field, dst_field]).size()
        for s in src_nodes:
            for d in dst_nodes:
                value = flows.get((s, d), 0)
                if not value:
                    continue
                h = value * scale
                src, dst = (src_field, s), (dst_field, d)
                category = s if src_field == "category" else d if dst_field == "category" else None
                colour = CATEGORY_COLOUR[category] if category else LIGHT
                ribbon(ax, xs[c] + bar, top[src] - out_offset[src], xs[c + 1], top[dst] - in_offset[dst], h,
                       colour, 0.75 if category else 1.0)
                out_offset[src] += h
                in_offset[dst] += h

    for (field, nodes), x in zip(columns, xs):
        for node in nodes:
            y, n = top[(field, node)], size[(field, node)]
            colour = CATEGORY_COLOUR[node] if field == "category" else DARK
            ax.add_patch(Rectangle((x, y - n * scale), bar, n * scale, facecolor=colour, edgecolor=DARK,
                                   linewidth=0.6, zorder=3))
            if field == "category":
                name = f"{CATEGORY_NAMES[node]} ({node})"
            elif field == "mechanism":
                name = mechanism_label(node, wrap=False)
            else:
                name = node
            label = name if field == "records" else f"{name}  {n:,}"
            left = field == "records"
            ax.text(x - 0.01 if left else x + bar + 0.008, y - n * scale / 2, label, ha="right" if left else "left",
                    va="center", fontsize=12.5 if field != "records" else 14, color=INK, zorder=4,
                    fontweight="bold" if field == "records" else "normal",
                    bbox=None if left or field == "mechanism" else
                    {"facecolor": SURFACE, "edgecolor": "none", "alpha": 0.8, "pad": 1.2})
    for x, heading in zip(xs, ("", "System", "EICAT category", "Mechanism")):
        ax.text(x, 1.035, heading, fontsize=15, fontfamily=style.HEADING, fontweight="bold", color=DARK)
    style.save(fig, out / "gisd_sankey.png")


# ── 3. the app pipeline ───────────────────────────────────────────────────────


def fig_pipeline(out: Path) -> None:
    fig, ax = canvas("EICAT-AI: from PDF to EICAT impact records",
                     "Five containerised services; the LLM call runs on AWS Bedrock.")
    steps = [
        ("Species + PDFs", "GBIF name lookup,\nuser uploads papers", LIGHT, INK),
        ("GROBID", "PDF → TEI XML:\nbody text, no references", LIGHT, INK),
        ("TEI → Markdown", "clean text for\nthe model", LIGHT, INK),
        ("LLM agent", "Claude Haiku 5.5\n(Pydantic AI)", GREEN, INK),
        ("Impact records", "mechanism · category\nconfidence · evidence", DARK, SURFACE),
    ]
    w, gap, y, h = 2.7, 0.55, 3.6, 2.0
    for i, (title, body, fill, text) in enumerate(steps):
        x = 0.25 + i * (w + gap)
        box(ax, x, y, w, h, title, body, fill, text)
        if i:
            arrow(ax, (x - gap, y + h / 2), (x, y + h / 2))
    agent_x = 0.25 + 3 * (w + gap)
    note_x, note_w, note_h = 6.6, 8.6, 2.5
    box(ax, note_x, 0.2, note_w, note_h, "EICAT guidelines distilled into the agent",
        "system prompt: category criteria and mechanism definitions\n"
        "typed output schema (EICAT enums) · 7 worked GISD examples\n"
        "mechanism synonym hints · one record per mechanism",
        fill=SURFACE, text=INK)
    ax.add_patch(FancyBboxPatch((note_x, 0.2), note_w, note_h, boxstyle="round,pad=0,rounding_size=0.18",
                                facecolor="none", edgecolor=GREEN, linewidth=2, linestyle=(0, (5, 3))))
    arrow(ax, (agent_x + w / 2, 0.2 + note_h), (agent_x + w / 2, y), colour=GREEN)
    last_x = 0.25 + 4 * (w + gap)
    ax.text(last_x + w / 2, y + h + 0.45, "reviewed in the web UI,\nlinked to source quotes", ha="center",
            va="bottom", fontsize=12, color=MUTED, linespacing=1.4)
    style.save(fig, out / "pipeline.png")


# ── 4. the GISD evaluation ────────────────────────────────────────────────────


def fig_eval_design(out: Path) -> None:
    fig, ax = canvas("Evaluating against GISD",
                     "Held-out test split; every paper goes through the running app exactly as a user upload would.")
    box(ax, 0.3, 4.2, 3.3, 1.7, "60 test papers", "held out from all tuning;\n80 GISD impacts", LIGHT, INK)
    box(ax, 0.3, 1.2, 3.3, 1.7, "GISD EICAT rows", "for each paper × species:\nthe gold impacts", LIGHT, INK)
    box(ax, 4.6, 4.2, 3.0, 1.7, "EICAT-AI app", "end to end:\nAPI → GROBID → LLM", GREEN, INK)
    box(ax, 8.6, 2.5, 3.3, 2.1, "LLM judge", "GPT-5.5 pairs each extracted\nimpact with a GISD impact\n"
                                              "describing the same effect", DARK, SURFACE)
    box(ax, 12.9, 4.2, 2.8, 1.7, "Detection", "precision · recall · F2\n(recall-weighted)", LIGHT, INK)
    box(ax, 12.9, 1.2, 2.8, 1.7, "Labels", "mechanism · category\non matched pairs", LIGHT, INK)
    arrow(ax, (3.6, 5.05), (4.6, 5.05))
    arrow(ax, (7.6, 5.05), (8.6, 4.1), connectionstyle="arc3,rad=-0.15")
    arrow(ax, (3.6, 2.05), (8.6, 3.0), connectionstyle="arc3,rad=0.15")
    arrow(ax, (11.9, 4.1), (12.9, 5.05), connectionstyle="arc3,rad=-0.15")
    arrow(ax, (11.9, 3.0), (12.9, 2.05), connectionstyle="arc3,rad=0.15")
    ax.text(8.6 + 1.65, 0.8, "unmatched extracted = false positive\nunmatched GISD = false negative",
            ha="center", fontsize=12, color=MUTED, linespacing=1.4)
    style.save(fig, out / "eval_design.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=EVAL / "figures_context")
    parser.add_argument("--bare", action="store_true", help="No in-figure titles, cropped; for slide decks.")
    args = parser.parse_args()

    style.apply(bare=args.bare)
    fig_scale(args.out)
    fig_gisd(args.out)
    fig_gisd_sankey(args.out)
    fig_pipeline(args.out)
    fig_eval_design(args.out)


if __name__ == "__main__":
    main()

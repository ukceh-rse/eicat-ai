"""Build the extraction prompt's few-shot examples from GISD expert assessments.

Each example is one GISD reference x species: its evidence passages stand in for the paper text and
its rows (merged across countries) are the expected Impact records. The examples are written to
`api/src/eicat_ai/fewshot_examples.json` with the exact GISD reference string, and `gisd_eval.py`
skips any PDF whose reference is used here, so an example can never be scored as an evaluation case.

The selected references were chosen because none of their PDFs are in `gisd_data/` (so no example
overlaps any evaluated paper) and together they cover the recording conventions GISD assessors use:
diet evidence as predation/grazing, hypothesised impacts as DD, null results as MC, one record per
mechanism and impacted taxon, and impacts reported second-hand in reviews or risk assessments.

    uv run --project eval eval/build_fewshot.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eicat_eval.gisd import merge_countries, read_gisd
from eicat_eval.paths import FEWSHOT_EXAMPLES, GISD_CLEAN

# (substring of the GISD reference, species)
SELECTED = [
    ("Linnebjerg J., Hansen D., Bunbury N. & Olesen J. (2010)", "Pycnonotus jocosus"),
    ("Kiesecker JM, Blaustein AR (1998)", "Lithobates catesbeianus"),
    ("Bissattini AM, Buono V, Vignoli L (2019)", "Lithobates catesbeianus"),
    ("Guillaume, G. et al. (2014)", "Cygnus olor"),
    ("Markula, A., Hannan-Jones, M. & Csurhes, S., (2009)", "Acridotheres tristis"),
    ("Faye, A., Krasova-Wade, T.", "Acacia holosericea"),
    ("CABI.  (2009). Invasive species compendium. Datasheet report for Anser indicus", "Anser indicus"),
]

APP_MECHANISMS = [
    "Competition", "Predation", "Hybridisation", "Transmission of diseases to native species", "Parasitism",
    "Poisoning/toxicity", "Bio-fouling", "Grazing/herbivory/browsing", "Chemical Impact on ecosystem",
    "Physical Impact on ecosystem", "Structural Impact on ecosystem", "Indirect impacts through interactions with other species",
]  # fmt: skip


def app_mechanism(gisd: str) -> str:
    """GISD spells some mechanisms differently ("Transmission of disease", "Bio-fouling or other ...")."""
    key = gisd.strip().lower()[:12]
    return next(m for m in APP_MECHANISMS if m.lower()[:12] == key)


def text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def build(gisd_path: Path) -> list[dict]:
    gisd = read_gisd(gisd_path)
    examples = []
    for ref_part, species in SELECTED:
        rows = gisd[gisd["Reference"].str.contains(ref_part, regex=False) & (gisd["Species"] == species)]
        refs = rows["Reference"].unique()
        if len(refs) != 1:
            sys.exit(f"{ref_part!r} / {species} matches {len(refs)} references")
        rows = merge_countries(rows)
        impacts = [
            {
                "alien_species": species,
                "mechanism": app_mechanism(r["Impact mechanism"]),
                "category": r["EICAT Category"],
                "evidence": text(r["Evidence for EICAT impact category"]),
                "confidence": text(r["Confidence rating"]).capitalize() or None,
                "justification": text(r["Justification for confidence rating"]),
                "impacted_species": [s.strip() for s in text(r["Impacted native species"]).split(",") if s.strip()],
            }
            for _, r in rows.iterrows()
        ]
        passages = list(dict.fromkeys(i["evidence"] for i in impacts if i["evidence"]))
        examples.append({"reference": refs[0], "species": species, "passages": passages, "impacts": impacts})
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gisd", type=Path, default=GISD_CLEAN)
    parser.add_argument("--out", type=Path, default=FEWSHOT_EXAMPLES)
    args = parser.parse_args()
    examples = build(args.gisd)
    args.out.write_text(json.dumps(examples, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(examples)} examples, {sum(len(e['impacts']) for e in examples)} impacts -> {args.out}")
    for e in examples:
        print(f"  {e['species']}: {', '.join(i['mechanism'] + '/' + i['category'] for i in e['impacts'])}")


if __name__ == "__main__":
    main()

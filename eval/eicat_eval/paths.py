"""Repository locations, and the default inputs and outputs of the evaluation scripts.

Every path is absolute, so scripts behave the same whatever directory they are run from.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVAL = REPO / "eval"
UTILS = REPO / "utils"

# GISD evaluation
GISD_DATA = REPO / "gisd_data"  # GISD export, cleaned CSV, reference library page and the PDFs (gitignored)
GISD_CLEAN = GISD_DATA / "gisd_clean.csv"
RUNS = EVAL / "runs"  # one directory per evaluation run (gitignored)
FEWSHOT_EXAMPLES = REPO / "api" / "src" / "eicat_ai" / "fewshot_examples.json"  # built by build_fewshot.py
COMPOSE_FILES = (REPO / "docker-compose.yml", EVAL / "compose.gisd-eval.yml")

# Inter-annotator agreement study
IAA_INPUT = REPO / "eval-data" / "iaa" / "batch_a"  # one annotator spreadsheet per file (gitignored)
ANNOTATOR_IDS = EVAL / "annotators.json"  # real initials -> anonymous id (gitignored, never commit)
ANNOTATOR_EXPERIENCE = EVAL / "annotator_experience.json"  # anonymous id -> "Skilled" / "Unskilled"
IAA_ALIGNMENT = EVAL / "iaa_alignment.csv"
IAA_METRICS = EVAL / "iaa_metrics.json"
CATEGORY_METRICS = EVAL / "category_metrics.json"
IAA_REPORT = EVAL / "iaa_report.md"
IAA_FIGURES = REPO / "docs" / "images"  # anonymised, safe to publish
IAA_FIGURES_NAMED = EVAL / "figures_named"  # real initials, local debugging only (gitignored)

# Figures
FONTS = EVAL / "fonts"  # static Gabarito and Work Sans instances for the brand style

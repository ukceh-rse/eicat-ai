# Evaluation: inter-annotator agreement

Tooling for the IAA study described in [`site/eval-protocol.qmd`](../site/eval-protocol.qmd).

Dependencies are managed by [`pyproject.toml`](pyproject.toml); run scripts with
`uv run --project eval eval/<script>.py` from the repo root, no separate install step.

Annotator files in `--input` (`eval-data/batch_a` by default) are matched by filename stem,
one file per annotator, `.xlsx` or `.csv`. Every script anonymizes that stem to an id like
`A1`, `A2`, ... via [`anonymize.py`](anonymize.py) before it touches any output, so no file
this pipeline writes (metrics, figures, `iaa_report.md`) ever carries an annotator's initials.
The real stem-to-id mapping lives in `annotators.json`, gitignored, and grows additively: an
id is assigned the first time its stem is seen and never changes, so ids stay stable across
scripts and across re-runs even as new annotators are added.

## `align_impacts.py` — impact alignment baseline

Before agreement can be measured on EICAT *labels* (category, mechanism, confidence), we
first need a more basic baseline: **do annotators even pick out the same underlying
impacts from a paper?**

Annotators phrase and split impacts differently — one may quote a passage verbatim and
record five separate impacts where another summarises the same paper as one — so the
evidence quotes cannot be matched by string comparison or row position. This script pools
every annotator's evidence quotes per paper and uses a Pydantic AI agent (Bedrock Claude,
temperature 0) to cluster quotes that describe the *same* impact, judged purely on the
evidence text. EICAT category and mechanism labels are ignored at this stage.

### Running

Needs AWS SSO login (Bedrock access):

```bash
uv run --project eval eval/align_impacts.py --input eval-data/batch_a
```

| Option | Default | Description |
|--------|---------|-------------|
| `--input` | `eval-data/batch_a` | Directory of annotator `.xlsx` or `.csv` files (one file per annotator). |
| `--output` | `eval/iaa_alignment.csv` | Where the cluster table is written. |
| `--metrics` | `eval/iaa_metrics.json` | Where the full metrics (pairwise scores, α, κ, distributions) are written. |
| `--model` | `bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0` | Pydantic AI model id used for clustering. |

Input spreadsheets must contain the columns `Species/Reference Text` and
`Evidence for EICAT impact category`; all other columns are ignored.

### What it produces

**`eval/iaa_alignment.csv`** — one row per distinct impact (cluster):

| Column | Description |
|--------|-------------|
| `paper` | Species / reference the impact was drawn from. |
| `summary` | Short LLM description of the shared underlying impact. |
| `n_annotators` | How many annotators identified this impact (1–N). |
| `annotators` | Comma-separated annotator ids that identified it. |
| `quote_ids` | The contributing evidence quotes, tagged `<annotator>-<row>`. |

**Console** — the headline: the number of impacts/papers/annotators and a summary of the
pairwise Jaccard scores (mean, median, standard deviation, and the best/worst scoring pair).
It also flags any quote the model assigned to multiple impacts (`·`) or left unassigned (`!`).

**`eval/iaa_metrics.json`** — all detection-agreement metrics, for later analysis:

| Key | Description |
|-----|-------------|
| `jaccard_summary` | Aggregate stats over the per-pair Jaccard scores: `n_pairs`, `mean`, `median`, `std`, and the `min`/`max` pair (the console figures). |
| `pairwise_jaccard` | Per annotator pair: `jaccard` (mean over the papers both annotated) and `n_shared_papers`. Restricting to shared papers makes it robust to partial coverage. |
| `krippendorff_alpha` | Chance-corrected agreement over the presence/absence matrix (unit = impact, rater = annotator). Handles annotators who did not cover a paper (treated as missing). |
| `fleiss_kappa` | Same matrix; `null` unless every annotator covered every paper (Fleiss requires complete coverage). |
| `agreement_distribution` | Count of impacts by number of agreeing annotators. |
| `per_paper` | Per paper: number of impacts and how many were unanimous. |

Expect α to read substantially lower than the Jaccard figures: the presence/absence matrix
is dominated by impacts only one annotator reported (largely a lumping-vs-splitting
difference), and the chance correction penalises that heavily.

### Caveats

- Being LLM-driven, cluster counts vary slightly between runs even at temperature 0.
- A single quote may legitimately span multiple impacts and is then credited to each.
- Agreement on the mechanism/confidence labels (for the impacts annotators *did* align on)
  is still not implemented. Agreement on EICAT category is covered separately, at the
  per-paper maximum, by `category_agreement.py` below.

The output CSV and metrics JSON are gitignored.

## `category_agreement.py` — maximum category per paper

A second, independent IAA angle: for each paper, does everyone agree on its *maximum*
EICAT category, i.e. the most severe impact found? This reads the `EICAT Category` column
directly (no LLM clustering needed) and takes each annotator's highest-ranked category per
paper (Minimal Concern < Minor < Moderate < Major < Massive; Data Deficient rows are
excluded from the ranking, since they represent no assessment rather than a severity).

Category values are normalised before matching (some annotators write `"MC - Minimal
Concern"`, others just `"Minimal Concern"`); anything that still doesn't match a known
category prints a `NOTE:` to the console naming the file and value, rather than silently
dropping that annotator's rows.

### Running

Pure pandas; no AWS access needed:

```bash
uv run --project eval eval/category_agreement.py --input eval-data/batch_a
```

### What it produces

**`eval/category_metrics.json`**:

| Key | Description |
|-----|-------------|
| `krippendorff_alpha` | Ordinal agreement over the paper x annotator max-category matrix. |
| `unanimous_papers` | How many papers had every annotator land on the same maximum category. |
| `mean_spread` | Average gap, in category steps, between annotators' max category on papers where they disagreed. |
| `per_paper` | Per paper: annotator count, distinct categories seen, unanimous flag, spread. |
| `data_deficient_counts` | How many rows per paper were rated Data Deficient (excluded from ranking). |
| `matrix` | Paper x annotator max-category rank, `null` where an annotator didn't rate that paper. Consumed by `report_iaa.py` for the heatmap. |

## `report_iaa.py` — figures and interpretation

Turns the metrics files above into report-ready figures and a short written interpretation,
no AWS access needed (pure `matplotlib`/`numpy`/`pandas` over the existing metrics files).

```bash
uv run --project eval eval/report_iaa.py
```

Always reads `iaa_metrics.json` and writes `iaa_pairwise_jaccard.png` (annotator x annotator
Jaccard heatmap) and `iaa_agreement_distribution.png` (impacts by number of agreeing
annotators). If `category_metrics.json` exists, it also writes `iaa_max_category.png` (paper
x annotator heatmap of maximum category). All headline numbers plus plain-language
interpretation, using the Landis & Koch (1977) bands from `site/eval-protocol.qmd`, are
written to `eval/iaa_report.md`. It also warns if `eval-data/batch_a` contains annotator
files not yet covered by the impact-alignment metrics, so stale figures don't go unnoticed
after `align_impacts.py` is re-run.

Every figure is written twice:

- **`docs/images/`** — anonymized (`A1`, `A2`, ...), safe to commit and put in the report.
- **`eval/figures_named/`** — the same figures with real initials instead, gitignored, for
  spotting annotator-specific data issues (e.g. a formatting quirk in one person's
  spreadsheet) that an anonymized chart makes hard to trace back to a source file.


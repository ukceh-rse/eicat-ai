# Evaluation

Tooling for the inter-annotator agreement (IAA) study described in
[`site/eval-protocol.qmd`](../site/eval-protocol.qmd), an end-to-end evaluation of the application
against GISD, and the figures used to present both.

Dependencies are managed by [`pyproject.toml`](pyproject.toml); run scripts from the repo root with
`uv run --project eval eval/<script>.py`, no separate install step.

## Layout

| | |
|---|---|
| [`eicat_eval/`](#the-eicat_eval-library) | Shared library: EICAT vocabulary, data loaders, agreement statistics, brand styling. |
| **GISD evaluation** | |
| [`gisd_eval.py`](#gisd_evalpy--end-to-end-evaluation-against-gisd) | Pipeline entry point: `fetch`, `extract`, `judge`, `score`, `report`, `run`. |
| `gisd_judge.py`, `gisd_score.py`, `gisd_report.py` | The `judge`, `score` and `report` stages, importable on their own. |
| [`gisd_compare.py`](#comparing-extraction-models) | Accuracy and cost table across scored runs. |
| [`build_fewshot.py`](#build_fewshotpy--few-shot-examples) | Builds the extraction prompt's few-shot examples from GISD. |
| **Inter-annotator agreement** | |
| [`align_impacts.py`](#align_impactspy--impact-alignment-baseline) | Clusters annotators' evidence quotes into shared impacts (LLM), then scores detection agreement. |
| [`category_agreement.py`](#category_agreementpy--maximum-category-per-paper) | Agreement on each paper's most severe category. |
| [`report_iaa.py`](#report_iaapy--figures-and-interpretation) | Report figures and a written summary of the two above. |
| [`iaa_experience.py`](#iaa_experiencepy--agreement-by-eicat-experience) | Agreement split by EICAT experience, with brand-styled figures. |
| `iaa_labels.py` | How pairs of annotators' category and mechanism labels compare for impacts they both found, by experience group. |
| **Presentation figures** | |
| [`present_*.py`](#presentation-figures) | Brand-styled 16:9 figures for talks. |
| [`tests/`](#tests) | Tests for the library. |

## The `eicat_eval` library

Everything more than one script needs lives in [`eicat_eval/`](eicat_eval/), so no script imports
another script's internals. Scripts import it as a sibling package (`from eicat_eval import eicat`);
each module's docstring documents it in full.

| Module | Contents |
|---|---|
| [`paths`](eicat_eval/paths.py) | Absolute repository locations and every script's default inputs and outputs. |
| [`eicat`](eicat_eval/eicat.py) | Category codes, names and severity order (`by_severity`), mechanism display labels. |
| [`gisd`](eicat_eval/gisd.py) | `read_gisd`, `merge_countries`, `gold_impacts`, `canonical_mechanism`; the one bridge into `utils/`. |
| [`annotators`](eicat_eval/annotators.py) | Anonymisation, `EXCLUDED` annotators, sheet loaders (`load_evidence`, `load_categories`), `max_category_matrix`, `drop_annotators`, `load_experience`. |
| [`agreement`](eicat_eval/agreement.py) | `presence_matrix`, `pairwise_jaccard`, `krippendorff_alpha`, `landis_koch`, `exact_permutation_p`. |
| [`runs`](eicat_eval/runs.py) | Reading scored runs: `read_metrics`, `read_cases`, `class_accuracy`. |
| [`style`](eicat_eval/style.py) | OneSTOP brand palette, fonts, `slide` layout and `save`; `apply(bare=True)` for slide decks. |
| [`charts`](eicat_eval/charts.py) | Shared chart components: `radar_axes`, `max_category_confusion`. |

### Annotator anonymity and exclusions

Annotator files in `--input` (`eval-data/iaa/batch_a` by default) are matched by filename stem,
one file per annotator, `.xlsx` or `.csv`. Every loader in `eicat_eval.annotators` anonymizes that
stem to an id like `A1`, `A2`, ... before it touches any output, so no file this pipeline writes
(metrics, figures, `iaa_report.md`) ever carries an annotator's initials. The real stem-to-id
mapping lives in `annotators.json`, gitignored, and grows additively: an id is assigned the first
time its stem is seen and never changes, so ids stay stable across scripts and re-runs.

Annotators listed in `EXCLUDED` in [`eicat_eval/annotators.py`](eicat_eval/annotators.py) (currently
A7, an outlier that overlapped with almost no other annotator on which impacts are present) are
dropped as their sheets are read, so they are left out of every IAA metric, figure and report.

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
uv run --project eval eval/align_impacts.py
```

| Option | Default | Description |
|--------|---------|-------------|
| `--input` | `eval-data/iaa/batch_a` | Directory of annotator `.xlsx` or `.csv` files (one file per annotator). |
| `--output` | `eval/iaa_alignment.csv` | Where the cluster table is written. |
| `--metrics` | `eval/iaa_metrics.json` | Where the full metrics (pairwise scores, α, κ, distributions) are written. |
| `--model` | `bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0` | Pydantic AI model id used for clustering. |
| `--reuse` | off | Skip clustering: recompute the metrics from the existing `--output` CSV, dropping excluded annotators (see below). No AWS access needed. |

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
uv run --project eval eval/category_agreement.py
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
written to `eval/iaa_report.md`. It also warns if `eval-data/iaa/batch_a` contains annotator
files not yet covered by the impact-alignment metrics, so stale figures don't go unnoticed
after `align_impacts.py` is re-run.

Every figure is written twice:

- **`docs/images/`** — anonymized (`A1`, `A2`, ...), safe to commit and put in the report.
- **`eval/figures_named/`** — the same figures with real initials instead, gitignored, for
  spotting annotator-specific data issues (e.g. a formatting quirk in one person's
  spreadsheet) that an anonymized chart makes hard to trace back to a source file.

## `iaa_experience.py` — agreement by EICAT experience

Splits the agreement study by annotators' EICAT experience ("Skilled": has performed EICAT
assessments; "Unskilled": familiar with EICAT but has not), from `annotator_experience.json`
(anonymous id -> level, taken from the Task 4.4 participation form). Reuses the clusters from
`align_impacts.py`, so it makes no model calls.

```bash
uv run --project eval eval/iaa_experience.py [--bare]
```

It writes `eval/iaa_experience_metrics.json` (pairwise Jaccard by pair type, Krippendorff's alpha
per group for impact presence and most severe category, Landis & Koch bands, per-annotator recall
of majority-agreed impacts) and five brand-styled figures to `eval/figures_iaa/`. Differences
between the groups get an exact permutation test over every way of splitting the annotators into
groups of the same sizes (`exact_permutation_p` in the metrics).

## `gisd_eval.py` — end-to-end evaluation against GISD

Benchmarks the **running application** rather than the extraction agent in isolation: each
paper takes the same path as a user upload (API → GROBID → TEI → Markdown → analysis) and the
impacts the app returns are scored against the GISD EICAT rows for that reference and species.
Needs Docker and AWS credentials with Bedrock access (the API container mounts `~/.aws` and
inherits `AWS_PROFILE`/`AWS_REGION`).

### 1. Fetch the GISD data

```bash
uv run --project eval eval/gisd_eval.py fetch
```

Runs the [`utils/`](../utils/README.md) scripts into `gisd_data/`:

- `gisd.xlsx` — latest GISD export (`--force` re-downloads)
- `gisd_clean.csv` — rows with an EICAT category (DD included), mechanisms normalised
- `references.html` — the reference library: one entry per reference with search links, the
  `PDF Filename` to save it as, whether that PDF is present, and its source URL

`references.html` is a single page built by [`utils/library.py`](../utils/README.md#4-reference-library);
its reference data is embedded in it, so it is also the manifest `run` reads. Files are named
`first_author_year.pdf`, suffixed where references collide (`lever_2005_a.pdf`, `_b`, ...) so each
name maps to exactly one reference. Re-running `fetch` refreshes the page and keeps every
filename and source URL already in it.

### 2. Add the PDFs

PDFs go **directly in `gisd_data/`** (flat, no subfolders), each named exactly as its filename in
the library. Open `gisd_data/references.html` to work through the list, or serve it to get live
availability and download-from-URL:

```bash
uv run utils/library.py serve gisd_data/references.html   # then open http://127.0.0.1:8765/
```

Only references with a PDF present are evaluated; PDFs not in the library are skipped with a
warning. `gisd_data/` is gitignored.

### 3. Run the pipeline

```bash
uv run --project eval eval/gisd_eval.py run
```

`run` chains four stages. Each stage reads the previous one's files from the run directory, so any
of them can be re-run on its own, e.g. to re-judge with another model or to tweak the report without
touching the app:

| Stage | Command | Reads | Writes | Needs |
|-------|---------|-------|--------|-------|
| 1. extract | `gisd_eval.py extract [--out DIR]` | PDFs, library, GISD CSV | `gold.csv`, `extracted/` | Docker, Bedrock |
| 2. judge | `gisd_eval.py judge DIR` | `gold.csv`, `extracted/` | `judged/` | Bedrock |
| 3. score | `gisd_eval.py score DIR` | `gold.csv`, `extracted/`, `judged/` | `metrics.json`, `cases.csv`, `pairs.csv`, `impacts.csv` | - |
| 4. report | `gisd_eval.py report DIR` | `metrics.json` | `report.md`, `figures/` | - |

The code follows the same split: [`gisd_eval.py`](gisd_eval.py) (CLI, fetch, extract),
[`gisd_judge.py`](gisd_judge.py), [`gisd_score.py`](gisd_score.py) and [`gisd_report.py`](gisd_report.py).

**extract** pairs each PDF with its GISD rows (one **case** per PDF × species), starts an isolated stack
(`docker compose -p eicat-gisd-eval` with [`compose.gisd-eval.yml`](compose.gisd-eval.yml):
its own Mongo volume, API on **18000**, no UI, so it runs alongside the dev stack), uploads
each paper and runs one analysis per species into `eval/runs/<timestamp>/`.

| Option (`extract`, `run`) | Default | Description |
|--------|---------|-------------|
| `--data-dir` | `gisd_data` | Where the PDFs are. |
| `--manifest` / `--gisd` | `<data-dir>/references.html` / `gisd_clean.csv` | Reference library page and gold rows. |
| `--out` | `eval/runs/<timestamp>` | Run directory. Pass an existing one to **resume**: only unfinished cases are re-run. |
| `--api-url` | `http://localhost:18000` | Eval stack API. |
| `--concurrency` | `4` | PDFs processed in parallel. |
| `--down` | off | Tear down the eval stack and its database afterwards. |

The extraction model is the API's default; set `EICAT_MODEL` in your shell to override it (it is passed
into the container and recorded in each result).

**judge** asks an LLM (Pydantic AI, temperature 0) to pair each case's extracted impacts with its GISD
impacts, one-to-one, as described in [`site/eval-protocol.qmd`](../site/eval-protocol.qmd#llm-as-judge-evaluation).
The judge sees only each impact's evidence text and impacted taxa: mechanism and category labels are
hidden, so that label agreement can be scored afterwards without the pairing being biased towards it.
Each pair carries a one-sentence `reason`. Judgements are cached per case and reused unless the case's
extraction is newer; pairs that reuse or invent an id are dropped with a `·` note.

| Option (`judge`, `run`) | Default | Description |
|--------|---------|-------------|
| `--judge-model` | `bedrock:global.openai.gpt-5.5` | Pydantic AI model id for the judge. |
| `--judge-concurrency` | `4` | Cases judged in parallel. |
| `--force-judge` | off | Re-judge cases that already have a judgement. |

### Metrics

Mechanism names from both sides are mapped onto the canonical GISD names (`utils/gisd.py`, plus the
app's `Bio-fouling`). Categories are ranked MV > MR > MO > MN > MC > DD throughout.

1. **Impact detection.** A judged pair is a true positive, an unpaired extracted impact a false
   positive, an unpaired GISD impact a false negative. Precision, recall, F1 and F2 (recall weighted
   higher), reported as micro (counts pooled over cases) and macro (mean of per-case scores; a case
   with nothing extracted scores precision 0).
2. **Per-class metrics** for EICAT category and mechanism, in two views:
   - *matched*: classification on judged pairs only. Given the impact was found, was its label right?
     Micro F1 here equals accuracy.
   - *detection*: over all impacts, where an impact counts towards a class only if it was paired *and*
     both sides gave it that label, so missed and spurious impacts count against their class.

   Each view gives per-class P/R/F1/F2 with GISD support, plus micro and macro (unweighted mean over the
   classes seen on either side) averages. The matched view also gives a confusion matrix.
3. **Maximum category per case.** The most severe GISD category vs the most severe extracted one:
   exact accuracy, counts over- and under-estimated, mean absolute distance in category steps, and a
   confusion matrix. A case with nothing extracted has maximum `none` and counts as under-estimated.

Cases whose conversion, analysis or judging failed are listed in the summary and report, and excluded.

### Outputs (in the run directory, gitignored)

| File | Contents |
|------|----------|
| `report.md` | The report: all three metric groups as tables, with the figures below. |
| `figures/` | Confusion matrices (category, mechanism, max category) and per-class F1 bars. |
| `metrics.json` | Every metric in the report, plus confusion matrices and failures. |
| `cases.csv` | Per case: impact counts, tp/fp/fn, P/R/F1/F2, max categories. |
| `pairs.csv` | Per judged pair: GISD vs extracted category and mechanism, judge's reason, both evidence texts. |
| `impacts.csv` | All extracted impacts, flattened, with the GISD row each was paired to. |
| `judged/<case>.json` | Judge output per case: model and pairs (indices into the case's GISD rows / extracted impacts). |
| `extracted/<case>.json` | Raw app result per case: status, error, model, impacts, token usage. |
| `gold.csv` | The GISD rows used as gold, with `case_id`. |

### Comparing extraction models

Run the pipeline once per model on the same papers (a subset directory of PDFs via `--data-dir`, with
`--manifest`/`--gisd` pointing at the full library), then compare the scored runs:

```bash
EICAT_MODEL=bedrock:eu.anthropic.claude-haiku-5-5 uv run --project eval eval/gisd_eval.py run \
  --data-dir gisd_data/sample20 --manifest gisd_data/references.html --gisd gisd_data/gisd_clean.csv --out eval/runs/cmp_haiku-5-5
uv run --project eval eval/gisd_compare.py eval/runs/cmp_* --out eval/runs/model_comparison.md
```

[`gisd_compare.py`](gisd_compare.py) tabulates detection P/R/F1 (with a 95% bootstrap interval over cases),
label accuracy and max-category agreement per run, and the extraction cost from the token usage the API
records per analysis, priced at rough Bedrock list prices kept in the script (`PRICES`; re-check them).

### Caveats

- GISD sometimes spells one reference several ways (`lever_2005_a`/`_b`/`_c`), each its own
  library entry, so save the PDF under every name you want evaluated.
- GISD gives no vernacular names, so analyses use the scientific name only.
- The judge is an LLM (by default GPT-5.5, a different family from the Claude and Nova extraction models, to
  limit self-preference); spot-check `pairs.csv` (and unpaired rows in `impacts.csv`). Gold rows that share
  one evidence passage but differ in mechanism cannot be told apart by the judge, which sees no labels.
- GISD records one assessor's reading of a paper and often a subset of its impacts, so extracted
  impacts GISD did not record count as false positives even when they are genuine; read precision
  with that in mind.
- The eval stack runs `mongo:8.2` rather than the `mongo:8.0.21` in `docker-compose.yml`:
  8.0.x refuses to start on Linux kernels >= 6.19
  ([SERVER-121912](https://jira.mongodb.org/browse/SERVER-121912)). Everything else is the
  same images and builds as the app.

## `build_fewshot.py` — few-shot examples

Builds `api/src/eicat_ai/fewshot_examples.json`, the worked examples in the extraction prompt, from
seven hand-picked GISD references whose PDFs are not in `gisd_data/`. `gisd_eval.py` skips any PDF
whose reference is a few-shot example, so an example is never scored.

```bash
uv run --project eval eval/build_fewshot.py
```

## Presentation figures

Three scripts draw 16:9 PNG figures in the OneSTOP brand style (`eicat_eval.style`); each takes
`--out DIR` and `--bare` (no in-figure title or subtitle, cropped, for slide decks whose slide
titles carry the message). `docs/llmsig/build.sh` runs them all for the talk.

| Script | Figures | Default output |
|---|---|---|
| `present_context.py` | The EICAT scale, the GISD data (bar charts and a Sankey diagram), the app pipeline and the evaluation design | `eval/figures_context/` |
| `present_figures.py` | The 60-paper test runs compared: detection, radar charts of accuracy per mechanism and per category, label accuracy, severity errors | `eval/figures_present/` |
| `present_best.py` | The best run alone: headline numbers, radar charts, most-severe-category confusion and distance | `eval/figures_best/` |

The runs compared are listed in `RUNS` in `present_figures.py` and `RUN` in `present_best.py`.

## Tests

The library has a pytest suite in [`tests/`](tests/); it needs no data, network or AWS access.

```bash
uv run --project eval pytest eval/tests
```


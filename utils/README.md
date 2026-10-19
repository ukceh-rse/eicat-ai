# EICAT Eval Data Pipeline

Scripts for building stratified evaluation batches from the GISD dataset.

## Pipeline

```
download.py → filter_clean.py → sankey.py → library.py → [researcher] → batch.py
```

All scripts are run from the `utils/` directory with `uv run`.

## Steps

### 1. Download
```bash
uv run download.py
```
Downloads the GISD EICAT dataset from the IUCN portal to `data/gisd.xlsx`.  
Use `--force` to re-download if the file already exists.

### 2. Filter & clean
```bash
uv run filter_clean.py
```
Filters to rows with EICAT categories (MC/MN/MO/MR/MV), drops rows missing key fields,
and normalises known inconsistencies in mechanism strings. Outputs `data/gisd_clean.csv`.

### 3. Sankey & percentages
```bash
uv run sankey.py --no-browser
```
Builds a Sankey diagram (References → Species → Systems → Categories → Mechanisms) from
deduplicated (species × reference) pairs, opens it in the browser, and saves:
- `data/sankey.html` — interactive diagram
- `data/percentages.json` — marginal and joint distributions used for stratification

### 4. Reference library
```bash
uv run library.py build --gisd ../data/gisd_clean.csv --output ../data/papers/references.html
uv run library.py serve ../data/papers/references.html      # open http://127.0.0.1:8765/
```
Builds a single HTML page that the researcher uses to find and collect the PDFs. It sits in the
folder the PDFs go in and lists one entry per unique reference with:
- search links (Google Scholar, Google filetype:pdf, Semantic Scholar, plus DOI/Unpaywall and any
  URL given in the reference)
- the filename to save the PDF as (`first_author_year.pdf`, suffixed `_a`, `_b`, … where
  references collide), with a copy button
- whether that PDF is present, with a link to open it, and the percentage of the library collected
- a **Source URL** box: paste the URL of the PDF and the server downloads it under the right name
  (rejecting HTML landing/paywall pages) and records the URL in the page

Present PDFs are shaded green when their saved URL downloads them and yellow when they were added
by hand or their URL failed. A reference that can't be found can be marked unavailable, which shades
it red; one not found yet is left unshaded. A PDF in the folder overrides the unavailable mark. The
summary counts each group.

Each searched reference (PDF present or marked unavailable) is badged with who searched for it:
*by human* for anything done through the page or saved into the folder by hand, *by AI* for
results an AI assistant recorded with
`uv run library.py mark <page> <file> --by ai [--source URL | --unavailable]`. The status filter
can show either group. A PDF the assistant located but couldn't download (e.g. the site blocks
scripts) is recorded with `--blocked --source URL`, so it shows under *Source URL saved, PDF
missing* for a human to fetch.

The reference data is embedded in the page as JSON, so the page is also the manifest that
`batch.py` and `eval/gisd_eval.py` read. Opened straight from disk it shows availability as of the
last build or save; `serve` checks the folder live and enables Source URL. `build` can be re-run
at any time: it keeps each reference's filename and source URL. `uv run library.py download <page>`
tries every recorded source URL, marks whether it gives a PDF, and saves the PDFs that are missing
(never overwriting one already there), e.g. to rebuild the library elsewhere.
All subcommands take `--help`.

### 5. Create batches
```bash
uv run batch.py --batches 5 --size 20
```
Reads `references.html`, treats references whose PDF is in the library folder as available, joins back to the cleaned GISD data, and creates
stratified batches in `data/batches/`. Each batch gets its own subfolder (`batch_a/`,
`batch_b/`, …) containing:
- `batch_a.xlsx` — species name, reference text, and PDF filename only (no EICAT labels)
- PDF copies from `data/papers/` matching the references in that batch

Stratification targets the joint (System × Category × Mechanism) distribution from
`percentages.json`. Papers are distributed round-robin across batches so every batch
closely mirrors the overall distribution. A deviation report is printed on completion.

Use `--seed N` for reproducibility. Use `--papers-dir` to override the PDF source path.

## Options

Each script accepts `--help` for a full option listing. The most common overrides:

| Option | Default |
|---|---|
| `--input` / `--output` | `data/gisd*.csv` / `data/*.xlsx` |
| `--references` | `data/papers/references.html` |
| `--gisd` | `data/gisd_clean.csv` |
| `--percentages` | `data/percentages.json` |
| `--output-dir` | `data/batches/` |
| `--papers-dir` | `data/papers/` |

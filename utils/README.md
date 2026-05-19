# EICAT Eval Data Pipeline

Scripts for building stratified evaluation batches from the GISD dataset.

## Pipeline

```
download.py → filter_clean.py → sankey.py → references.py → [researcher] → batch.py
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

### 4. References spreadsheet
```bash
uv run references.py
```
Produces `data/references.xlsx` with one row per unique reference containing a clickable
Google Scholar link, a suggested PDF filename (`first_author_year.pdf`), and an empty
**Available** column (Y/N dropdown).

**Hand this file to a researcher** to locate and download PDFs, marking each as Y or N.

### 5. Create batches
```bash
uv run batch.py --batches 5 --size 20
```
Reads the marked `references.xlsx`, joins back to the cleaned GISD data, and creates
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
| `--references` | `data/references.xlsx` |
| `--gisd` | `data/gisd_clean.csv` |
| `--percentages` | `data/percentages.json` |
| `--output-dir` | `data/batches/` |
| `--papers-dir` | `data/papers/` |

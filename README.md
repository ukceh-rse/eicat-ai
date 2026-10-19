# EICAT AI

AI-powered tools for automating [Environmental Impact Classification for Alien Taxa (EICAT)](https://www.iucngisd.org/gisd/) assessments. Uses LLMs to extract and classify impact data from scientific literature.

## Quick Start

Requires Docker and AWS credentials with Bedrock access.

Create a `.env` file:

```bash
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=eu-west-2
```

Start all services:

```bash
docker compose up -d --build
```

- **Web UI**: http://localhost:8080
- **API docs**: http://localhost:8000/docs

## Services

| Service | Port | Description |
|---------|------|-------------|
| eicat-ai-api | 8000 | FastAPI backend — data upload, LLM processing |
| eicat-ai-ui | 8080 | React web interface |
| grobid | 8070 | PDF → TEI XML extraction |
| tei-stylesheets-api | 8001 | TEI XML → Markdown conversion |

## Workflow

1. Upload a scientific PDF via the web UI
2. GROBID extracts text; TEI service converts to Markdown
3. LLM extracts impact data from the document
4. Impacts are classified according to EICAT standards
5. Generate a standardised assessment report

## Evaluation

`eval/gisd_eval.py` benchmarks the full application stack against the GISD EICAT assessments: it starts an isolated copy of the stack, uploads manually downloaded papers through the API, runs an analysis per species, has an LLM judge pair the extracted impacts with GISD's, and writes a scored report.

```bash
uv run --project eval eval/gisd_eval.py fetch   # latest GISD data + reference library page into gisd_data/
uv run utils/library.py serve gisd_data/references.html  # find papers, download PDFs into gisd_data/
uv run --project eval eval/gisd_eval.py run     # start stack, extract, judge, score, report
```

The report (`eval/runs/<run>/report.md`) covers impact detection P/R/F1/F2, per-class metrics for EICAT category and mechanism, and maximum-category accuracy; each stage can also be run on its own. See [`eval/README.md`](eval/README.md#gisd_evalpy--end-to-end-evaluation-against-gisd) for details.

**Stack**: Python 3.13, FastAPI, Pydantic AI, React 19, TypeScript, AWS Bedrock (Claude 3.7 Sonnet / Nova Lite)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local development setup.
=======
# Deployment
- For deployment instructions see [infrastructure/README.md](infrastructure/README.md).

# Docs
The documentation site, including the presentation (`/docs/llmsig`), is built with quarto from the source files in `/docs`. The presentation's figures are generated rather than committed, so build them first, then preview or publish the site to the `gh-pages` branch:
```bash
docs/llmsig/build.sh
quarto preview docs
quarto publish gh-pages docs
```

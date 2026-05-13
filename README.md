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

Evaluation scripts benchmark the data extraction pipeline against gold standard GISD data. Docker services must be running.

Install the CLI:

```bash
uv pip install -e ./api
```

Run the three evaluation stages in order:

```bash
eicat-eval fetch    # download gold standard data from GISD
eicat-eval prepare  # process PDFs with GROBID
eicat-eval run      # compare LLM output against gold standard
```

After `fetch`, manually download the PDF files for each reference and place them in their respective directories before running `prepare`.

Results report precision, recall, and F1 scores.

**Stack**: Python 3.13, FastAPI, Pydantic AI, React 19, TypeScript, AWS Bedrock (Claude 3.7 Sonnet / Nova Lite)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local development setup.
=======
# Deployment
- For deployment instructions see [infrastructure/README.md](infrastructure/README.md).

# Docs
The documentation site is built with quarto. The source files can be found in `/site` and the web pages can be rendered to the `/docs` folder using:
```bash
quarto render site
```

# Contributing

## Local Development

### API

```bash
cd api
uv sync
uv run uvicorn eicat_ai.main:app --reload
```

### UI

```bash
cd ui
npm install
npm run dev
```

The API and UI can be run locally without Docker, but GROBID and the TEI Stylesheets API are easiest to run via Docker Compose:

```bash
docker compose up -d grobid tei-stylesheets-api
```

## Project Structure

```
eicat-ai/
├── api/                    # FastAPI backend
│   ├── eicat_ai/          # Main package
│   └── pyproject.toml
├── ui/                     # React frontend
│   ├── src/
│   └── package.json
├── tei-stylesheets-api/   # TEI XML → Markdown service
├── infrastructure/         # Terraform configs
└── docker-compose.yml
```

## Dependencies

- Python 3.13+, [uv](https://github.com/astral-sh/uv)
- Node.js 18+, npm 9+
- Docker (for GROBID and TEI services)
- AWS account with Bedrock access (Claude 3.7 Sonnet and Nova Lite enabled)

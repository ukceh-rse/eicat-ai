# EICAT AI API

FastAPI service for AI-assisted EICAT assessment generation. Provides document upload, analysis, and species lookup capabilities.

## Features

- **Document Analysis**: Upload PDFs and extract impact data using AI
- **Species Lookup**: Search GBIF database for species information  
- **File Management**: Upload and retrieve research documents

## Quick Start

### Local Development
```bash
uv sync
uv run src/eicat_ai/main.py
```

### Docker
```bash
docker build -t eicat-ai .
docker run -p 8000:8000 eicat-ai
```

API available at http://localhost:8000

## Dependencies

- [uv](https://docs.astral.sh/uv/) - Python package manager
- FastAPI - Web framework
- Pydantic AI - AI agent framework

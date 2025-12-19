# EICAT AI

AI-powered tools for automating Environmental Impact Classification for Alien Taxa (EICAT) assessments.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/) [![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)

## 📖 About

The **Environmental Impact Classification for Alien Taxa (EICAT)** is a standardized framework used by the IUCN to classify the environmental impacts of invasive alien species. This tool leverages Large Language Models (LLMs) to automate the extraction and classification of impact data from scientific literature, significantly reducing the time and effort required to conduct comprehensive EICAT assessments.

### Key Benefits

- 🚀 **Automated Data Extraction**: Extract impact data from scientific papers using AI
- 📊 **Standardized Classification**: Automatically classify impacts according to EICAT standards
- 📄 **PDF Processing**: Extract and process text from scientific literature
- ✅ **Quality Assurance**: Built-in evaluation framework to validate extraction accuracy
- 📝 **Report Generation**: Generate standardized EICAT assessment reports

## 📑 Table of Contents

- [About](#-about)
- [Features](#-features)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Installation & Quick Start](#-installation--quick-start)
- [Usage](#-usage)
- [Evaluation](#-evaluation)
- [Deployment](#-deployment)
- [Development](#-development)
- [License](#-license)

## ✨ Features

- 📄 **PDF Processing**: Automatic extraction of text from scientific papers using GROBID
- 🤖 **AI-Powered Extraction**: LLM-based data extraction for impact assessments using Pydantic AI
- 🏷️ **Classification**: Automated classification of environmental impacts following EICAT standards
- 📊 **Report Generation**: Template-based EICAT assessment report generation
- ✅ **Evaluation Framework**: Built-in tools to validate extraction accuracy against gold standard data
- 🌐 **Web Interface**: User-friendly React-based UI for managing assessments
- 🔌 **RESTful API**: FastAPI-based backend for programmatic access
- 🔄 **TEI Processing**: Convert between TEI XML and Markdown formats

## 🏗️ Architecture

```
┌─────────────┐      ┌──────────────┐      ┌────────────┐
│   React UI  │─────▶│  FastAPI API │─────▶│    LLM     │
│  (Port 8080)│      │  (Port 8000) │      │ (Pydantic) │
└─────────────┘      └──────────────┘      └────────────┘
                            │
                            ├─────────▶ GROBID (Port 8070)
                            │           PDF → TEI XML
                            │
                            └─────────▶ TEI Stylesheets API (Port 8001)
                                        XML → Markdown
```

### Technology Stack

- **Backend**: Python 3.13+, FastAPI, Pydantic AI
- **Frontend**: React 19, TypeScript, Vite, TailwindCSS
- **LLM Integration**: AWS Bedrock (Claude 3.7 Sonnet, Nova Lite) via Pydantic AI
- **Document Processing**: GROBID, TEI Stylesheets
- **Data Sources**: GISD (Global Invasive Species Database), GBIF

## 📋 Prerequisites

### For Running with Docker (Production/Quick Start)

- **[Docker](https://docs.docker.com/get-docker/)** (version 20.10 or higher)
- **[Docker Compose](https://docs.docker.com/compose/install/)** (version 2.0 or higher)

### For Development

If you want to run services locally without Docker or contribute to the project:

- **[Python 3.13+](https://www.python.org/downloads/)** - Required for API development
- **[uv](https://github.com/astral-sh/uv)** - Fast Python package manager (recommended for Python dependency management)
- **[Node.js](https://nodejs.org/)** (version 18.0 or higher) - Required for UI development
- **[npm](https://www.npmjs.com/)** (version 9.0 or higher) - Comes with Node.js, used for managing frontend dependencies

### For Running Evaluations

- **[uv](https://github.com/astral-sh/uv)** or **pip** - To install the evaluation CLI
- Docker services running (API, GROBID, TEI Stylesheets)

## 🚀 Installation & Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/eicat-ai.git
cd eicat-ai
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory with your AWS credentials:

```bash
# AWS Configuration (required for Bedrock LLM access)
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=eu-west-2  # or your preferred AWS region with Bedrock access
```

> **Note**: The application uses AWS Bedrock models (Claude 3.7 Sonnet and Nova Lite). Ensure your AWS account has access to Amazon Bedrock and the required models are enabled in your region.

### 3. Start All Services

```bash
docker compose up -d --build
```

This will build and start all services in detached mode. The first build may take several minutes.

### 4. Verify Services Are Running

```bash
docker compose ps
```

All services should show status as "Up" or "running".

### 5. Access the Application

- **Web UI**: http://localhost:8080
- **API**: http://localhost:8000/docs

## 📘 Usage

### Services Overview

The application consists of 4 main services:

| Service | Port | Description |
|---------|------|-------------|
| **eicat-ai-api** | 8000 | Main API for data upload, analysis requests, and LLM processing |
| **eicat-ai-ui** | 8080 | React-based web interface for the application |
| **grobid** | 8070 | Service for extracting text from PDFs and converting to TEI XML |
| **tei-stylesheets-api** | 8001 | Converts TEI XML to simplified Markdown for LLM processing |

### Basic Workflow

1. **Upload a PDF**: Upload scientific papers through the web UI
2. **Process Document**: The system extracts text using GROBID and converts it to Markdown
3. **Extract Data**: AI extracts impact data from the processed text
4. **Classify Impacts**: Impacts are automatically classified according to EICAT standards
5. **Generate Report**: Create a standardized EICAT assessment report

### Stopping Services

To stop all services:

```bash
docker compose down
```

To stop and remove all data and volumes:

```bash
docker compose down -v
```

### Viewing Logs

To view logs for all services:

```bash
docker compose logs -f
```

To view logs for a specific service:

```bash
docker compose logs -f eicat-ai-api
```

## 🧪 Evaluation

The repository contains evaluation scripts to test the performance of the data extraction module against gold standard data from GISD.

> **Note**: Evaluation commands can be run as `eicat-eval` if installed locally, or with `uv run eicat-eval` if using the uv package manager without installation.

### Prerequisites for Evaluation

1. Ensure Docker services are running (see [Installation](#-installation--quick-start))
2. Install the evaluation CLI:

```bash
# Using pip
pip install -e ./api

# Or using uv
uv pip install -e ./api
```

### Evaluation Workflow

The evaluation process is split into 3 stages:

#### 1. Fetch Gold Standard Data

Retrieve evaluation data from GISD (Global Invasive Species Database):

```bash
eicat-eval fetch
# or: uv run eicat-eval fetch
```

This will:
- Download the latest data from GISD
- Create a directory structure organized by reference ID
- Generate `gold_impacts_$SPECIES_NAME.csv` files containing manually extracted impacts
- Create `reference.html` files with Google Scholar links to help locate PDFs

**Next step**: Manually download the PDF files for the references you want to evaluate and place them in their respective directories.

#### 2. Prepare Evaluation Data

Process the downloaded PDFs for evaluation:

```bash
eicat-eval prepare
# or: uv run eicat-eval prepare
```

This will:
- Find all PDF documents in the evaluation directory
- Process them using GROBID to extract text
- Convert to TEI XML format
- Generate HTML and Markdown versions for LLM processing

#### 3. Run Evaluations

Execute the evaluation and compare results:

```bash
eicat-eval run
# or: uv run eicat-eval run
```

This will:
- Run the data extraction pipeline on prepared documents
- Compare LLM-extracted data with gold standard data
- Print detailed results to the console, including precision, recall, and F1 scores

## 🚀 Deployment

The EICAT-AI application can be deployed to AWS infrastructure using Terraform.

For detailed deployment instructions, see **[infrastructure/README.md](infrastructure/README.md)**.

## 🛠️ Development

### Development Setup

For local development without Docker:
#### API
```bash
cd api
uv sync
uv run eicat_ai.main:app --reload
```
#### UI
```bash
# Install UI dependencies
cd ui
npm install
npm run dev
```

### Project Structure

```
eicat-ai/
├── api/                    # FastAPI backend
│   ├── eicat_ai/          # Main package
│   └── pyproject.toml     # Python dependencies
├── ui/                     # React frontend
│   ├── src/               # Source files
│   └── package.json       # Node dependencies
├── tei-stylesheets-api/   # TEI conversion service
├── infrastructure/         # Terraform deployment configs
└── docker-compose.yml     # Local development setup
```

### Roadmap

- [ ] Search string module - Generate optimized search queries for literature review
- [ ] Paper retrieval module - Automatically retrieve papers from databases
- [ ] Paper summary and screening module - AI-assisted paper screening
- [x] Data extraction module - Extract impact data from papers
- [x] Data classification module - Classify impacts according to EICAT
- [x] Report template generation module - Generate standardized reports
- [ ] Terminology checker module - Validate EICAT terminology usage

## 📄 License

[Specify your license here - e.g., MIT, Apache 2.0, GPL-3.0]

## 📞 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/eicat-ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/eicat-ai/discussions)

## 🙏 Acknowledgments

This project uses:
- [GROBID](https://github.com/kermitt2/grobid) - Machine learning library for extracting structured data from technical documents
- [Pydantic AI](https://ai.pydantic.dev/) - Framework for building production-ready LLM applications
- [GISD](http://www.iucngisd.org/gisd/) - Global Invasive Species Database

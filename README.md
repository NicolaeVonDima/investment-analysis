# Investment Analysis Platform

A Docker-first investment analysis platform that takes a public stock ticker as input and produces a structured, reproducible investment memorandum (JSON + PDF). The system is designed for long-term, rules-based investing and emphasizes transparency, auditability, and deterministic outputs.

## Architecture

The platform consists of:

- **Frontend** (React + Vite): Modern web UI for browsing and analyzing investments
- **Web Application** (FastAPI): Handles user input, orchestration, and document delivery
- **Database** (PostgreSQL): Stores analysis requests and results
- **Worker Service** (Celery): Background processing for data fetching, metric computation, narrative generation, and PDF rendering
- **Redis**: Task queue broker for Celery
- **n8n** (optional): Workflow automation platform for webhooks, external integrations, and automated workflows

All services run locally via Docker Compose and are designed to scale independently in cloud deployments.

## Key Principles

1. **Reproducibility**: All analytics are derived from versioned rulesets and explicitly defined metrics
2. **Transparency**: All claims in narratives must be traceable to computed inputs
3. **Determinism**: Outputs conform to a fixed JSON schema before rendering
4. **Auditability**: Complete audit trail of data sources, computation steps, and ruleset versions
5. **No Speculation**: Strict guardrails prevent invented numbers or predictions

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/NicolaeVonDima/investment-analysis.git
cd investment-analysis
```

2. Start all services:
```bash
docker-compose up --build
```

3. Access the application:
- **Web UI**: `http://localhost:3000` - Modern React-based interface
- **API**: `http://localhost:8000` - REST API endpoints
- **n8n**: `http://localhost:5678` - Workflow automation (optional; default credentials: admin/changeme)

### API Documentation

Once running, visit:
- **Web UI**: `http://localhost:3000` - Interactive investment analysis interface
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Usage

### Submit an Analysis

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'
```

Response:
```json
{
  "job_id": 1,
  "ticker": "AAPL",
  "status": "pending",
  "message": "Analysis queued for processing"
}
```

### Check Status

```bash
curl "http://localhost:8000/api/status/1"
```

### Retrieve Results

**JSON:**
```bash
curl "http://localhost:8000/api/result/1/json" -o memorandum.json
```

**PDF:**
```bash
curl "http://localhost:8000/api/result/1/pdf" -o memorandum.pdf
```

## Project Structure

```
investment-analysis/
├── app/
│   ├── main.py              # FastAPI application
│   ├── database.py          # Database configuration
│   ├── models.py            # Database models
│   ├── schemas.py           # JSON schema definitions
│   ├── services/
│   │   ├── data_fetcher.py      # Market data fetching
│   │   ├── metric_computer.py   # Metric computation
│   │   ├── narrative_generator.py # Narrative generation
│   │   └── pdf_generator.py      # PDF rendering
│   └── worker/
│       ├── main.py          # Celery app
│       └── tasks.py         # Background tasks
├── rulesets/                # Versioned ruleset definitions
│   └── 1.0.0.json
├── templates/               # PDF and prompt templates
│   ├── memorandum.html
│   └── prompts.json
├── output/                  # Generated memorandums (gitignored)
├── docker-compose.yml
├── Dockerfile.web
├── Dockerfile.worker
├── requirements.txt
└── README.md
```

## Components

### Rulesets

Rulesets define which metrics to compute and how. They are versioned JSON files in the `rulesets/` directory. Each ruleset specifies:
- Metric definitions (name, description, category, formula, unit)
- Version number for tracking

### Templates

- **PDF Template** (`templates/memorandum.html`): Jinja2 template for PDF generation
- **Prompts** (`templates/prompts.json`): Narrative generation prompts with constraints

### Services

- **DataFetcher**: Fetches market data (currently using yfinance, designed to be replaceable)
- **MetricComputer**: Computes metrics using versioned rulesets
- **NarrativeGenerator**: Generates narrative sections with strict guardrails
- **PDFGenerator**: Renders PDFs from JSON memorandums

## Development

### Running Locally (without Docker)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start PostgreSQL and Redis:
```bash
docker-compose up db redis
```

3. Run migrations:
```bash
# Database tables are auto-created on startup
```

4. Start web server:
```bash
uvicorn app.main:app --reload
```

5. Start worker (in separate terminal):
```bash
celery -A app.worker.main worker --loglevel=info
```

### Adding New Metrics

1. Edit or create a new ruleset file in `rulesets/`
2. Add metric definition with name, description, category, formula, and unit
3. Implement computation logic in `app/services/metric_computer.py`

### Adding New Narrative Sections

1. Edit `templates/prompts.json`
2. Add new section definition with title and template
3. Update `app/services/narrative_generator.py` if needed

## Deployment

The architecture is designed to evolve from local Docker to cloud deployment with minimal refactoring:

- **Local**: Docker Compose (current)
- **Cloud Options**: Fly.io, Render, AWS ECS

Services can be scaled independently:
- Web: Multiple instances behind load balancer
- Worker: Horizontal scaling based on queue depth
- Database: Managed PostgreSQL service

## Data Providers

Currently uses `yfinance` for market data. The `DataFetcher` service is designed to be replaceable with other providers (Alpha Vantage, IEX Cloud, etc.) without architectural changes.

## Versioning

- **Rulesets**: Versioned in `rulesets/` directory
- **Prompts**: Versioned in `templates/prompts.json`
- **Schema**: Versioned in `app/schemas.py` (InvestmentMemorandum.version)

All outputs include version information for reproducibility and comparison over time.

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]


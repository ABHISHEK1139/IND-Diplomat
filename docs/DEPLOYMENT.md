# DIP 2.0 — Deployment Guide

## Quick Start

```bash
cd dip2.0
pip install -e .
python run.py "Assess border tensions" --country IND
```

## Docker Deployment

```bash
docker-compose up -d
```

Services:
- `web` — FastAPI on port 8000
- `worker` — Background job processor
- `guardian` — Health monitoring

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `gpt-4o` | LLM model for ministers |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `DIP_JOB_STORE` | `data/jobs.json` | Job persistence path |
| `DIP_OTEL_ENABLED` | `0` | Enable OpenTelemetry |
| `DIP_MLFLOW_ENABLED` | `0` | Enable MLflow |
| `DIP_LANGGRAPH_ENABLED` | `0` | Enable LangGraph runtime |
| `DIP_PREFECT_ENABLED` | `0` | Enable Prefect workflows |
| `FORCE_MINISTER_HEURISTIC` | `0` | Offline minister testing |

## Optional Dependencies

```bash
pip install -e ".[streaming]"    # Prefect + Bytewax
pip install -e ".[calibration]"  # MLflow + sklearn + Evidently + PyMC
pip install -e ".[legal]"        # Haystack + ChromaDB + txtai + sentence-transformers
pip install -e ".[observability]" # OpenTelemetry + Langfuse
pip install -e ".[intel-sharing]" # STIX2 + TAXII
pip install -e ".[dev]"          # Tests + linting + security
```

## Production Checklist

- [ ] Set `OPENROUTER_API_KEY` or equivalent
- [ ] Enable OpenTelemetry (`DIP_OTEL_ENABLED=1`)
- [ ] Enable LangGraph for durable execution (`DIP_LANGGRAPH_ENABLED=1`)
- [ ] Configure Prometheus + Grafana (see `deploy/prometheus.yml`)
- [ ] Run security scan: `bandit -r . && safety check`
- [ ] Set up Prefect server for scheduled workflows
- [ ] Index treaties into ChromaDB for legal RAG


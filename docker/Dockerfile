# =============================================================================
# Politiq AI — All-in-One
# Build context is the repository root:
#   docker build -f docker/Dockerfile -t politiq-ai:all .
# Run:    docker run -p 8000:8000 --env-file .env politiq-ai:all
# =============================================================================

FROM python:3.12-slim

LABEL maintainer="DIP Team"
LABEL service="dip-all"
LABEL role="all-in-one"
LABEL description="Politiq AI All-in-One — Web + Worker + Guardian + Scheduler (full stack)"

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl cron procps && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# DIP 3 package layout (src/dip); ASGI target is dip.api.rest_api:app.
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .
COPY scripts/ scripts/
RUN mkdir -p /app/data
ENV DIP_DATA_DIR=/app/data

EXPOSE 8000
ENV PYTHONUNBUFFERED=1
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
# Single worker: the JSON job stores support exactly one API process.
# Scale out only after migrating to Postgres/Redis-backed stores.
CMD ["python", "-m", "uvicorn", "dip.api.rest_api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

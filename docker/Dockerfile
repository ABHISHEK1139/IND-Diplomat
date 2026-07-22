# =============================================================================
# DIP 2.0 — All-in-One — ~1.4 GB
# Build:  docker build -t dip2-all .
# Run:    docker run -p 8000:8000 --env-file .env dip2-all
# =============================================================================

FROM python:3.12-slim

LABEL maintainer="DIP 2.0 Team"
LABEL service="dip2-all"
LABEL role="all-in-one"
LABEL description="DIP 2.0 All-in-One — Web + Worker + Guardian + Scheduler (full stack)"

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl cron procps && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data

EXPOSE 8000
ENV PYTHONUNBUFFERED=1
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# ============================================================================
# IND-Diplomat — Production Container
# ============================================================================
# Multi-stage build for a lean, secure runtime image.
#
# Usage:
#   docker build -t ind-diplomat .
#   docker run -p 8000:8000 --env-file .env ind-diplomat
#
# Or with docker compose:
#   docker compose up --build
# ============================================================================

# ── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for compilation (numpy, cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY Config/requirements.txt /build/requirements.txt

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="ABHISHEK1139"
LABEL description="IND-Diplomat — Geopolitical Intelligence Engine"
LABEL org.opencontainers.image.source="https://github.com/ABHISHEK1139/IND-Diplomat"

# Security: run as non-root
RUN groupadd --gid 1001 diplomat \
    && useradd --uid 1001 --gid diplomat --create-home --shell /bin/bash diplomat

# Runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy application code
COPY . /app

# Ensure runtime directories exist
RUN mkdir -p /app/runtime /app/data \
    && chown -R diplomat:diplomat /app/runtime /app/data

USER diplomat

# Health check — uses the existing /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# tini as init system for proper signal handling
ENTRYPOINT ["tini", "--"]

CMD ["python", "app_server.py", "--host", "0.0.0.0", "--port", "8000"]

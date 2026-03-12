# ── SyncFlow Customer Success API — Production Dockerfile ────────────────────
# Multi-stage build for minimal final image.
# Compatible with: Hugging Face Spaces (Docker SDK), Docker, Railway, Fly.io
#
# Hugging Face Spaces requirements:
#   - SDK:  Docker
#   - Port: 7860  (set PORT=7860 in Space secrets — already the default here)
#   - The Space will auto-build and serve this Dockerfile on push.

# ── Stage 1: Build ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Build-time system deps (gcc for psycopg2 compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system deps (libpq5 for psycopg2, curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Make startup script executable BEFORE switching to non-root user
RUN chmod +x /app/startup.sh

# Create non-root user (UID 1000 is compatible with HF Spaces)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# ── Environment defaults ──────────────────────────────────────────────────────
# All of these can be overridden via Hugging Face Space secrets or docker run -e.
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    DATABASE_URL="sqlite:///./syncflow_dev.db" \
    KAFKA_MOCK_MODE="true" \
    WORKERS=1

# WORKERS=1 is correct for:
#   - SQLite (single-writer; multiple workers cause locking errors)
#   - HF Spaces free tier (limited CPU; 1 worker is sufficient)
# For PostgreSQL + production: increase to 2-4 via the WORKERS secret.

# ── Health check ──────────────────────────────────────────────────────────────
# HF Spaces uses this to determine if the container is healthy.
# start-period=30s accounts for cold-start seed time.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Port 7860 is required by Hugging Face Spaces
EXPOSE 7860

# ── Startup ───────────────────────────────────────────────────────────────────
# startup.sh:
#   1. Seeds demo data (non-fatal — API starts even if seed fails)
#   2. Starts uvicorn with exec (proper signal handling for SIGTERM)
CMD ["/app/startup.sh"]

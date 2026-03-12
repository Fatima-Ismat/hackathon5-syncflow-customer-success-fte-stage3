#!/bin/sh
# startup.sh — SyncFlow Customer Success API
# Runs inside the Docker container on Hugging Face Spaces (and local Docker).
#
# Usage: called automatically by Dockerfile CMD
# Manual: sh startup.sh   (inside the container)

set -e

echo "============================================================"
echo " SyncFlow Customer Success Digital FTE — Stage 3"
echo " Owner: Ismat Fatima / NovaSync Technologies"
echo "============================================================"
echo ""
echo "[startup] PORT         = ${PORT:-7860}"
echo "[startup] DATABASE_URL = ${DATABASE_URL:-sqlite:///./syncflow_dev.db (default)}"
echo "[startup] KAFKA_MOCK   = ${KAFKA_MOCK_MODE:-true}"
echo "[startup] WORKERS      = ${WORKERS:-1}"
echo ""

# ── Step 1: Seed the database ─────────────────────────────────────────────────
# Non-fatal: seed fails gracefully if DB is unavailable or already seeded.
# The API works without seed data — it will start clean.
echo "[startup] Seeding database with demo data..."
python database/seed.py && echo "[startup] Seed complete." \
  || echo "[startup] Seed skipped or failed — API will start anyway. (This is normal on first cold start.)"

echo ""
echo "[startup] Starting SyncFlow API on port ${PORT:-7860}..."
echo "[startup] Swagger UI will be at: http://localhost:${PORT:-7860}/docs"
echo ""

# ── Step 2: Start API ─────────────────────────────────────────────────────────
# exec replaces the shell process so the API receives signals cleanly (SIGTERM, etc.)
exec uvicorn api.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-7860}" \
  --workers "${WORKERS:-1}" \
  --log-level info

#!/bin/bash
# ─────────────────────────────────────────────────────────
# run.sh — Start the UC Automation Portal with Gunicorn
# Usage: ./run.sh
# ─────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
WORKERS="${WORKERS:-2}"

# Activate virtual environment
if [ -d "venv" ]; then
  source venv/bin/activate
elif [ -d ".venv" ]; then
  source .venv/bin/activate
else
  echo "⚠  No virtual environment found. Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# Initialise database on first run
python -c "from app import app; from database.models import db; \
  app.app_context().push(); db.create_all(); print('✓ Database ready.')"

echo "─────────────────────────────────────────────"
echo "  UC Automation Portal"
echo "  http://${HOST}:${PORT}"
echo "  Workers: ${WORKERS}"
echo "─────────────────────────────────────────────"

exec gunicorn \
  --workers "$WORKERS" \
  --bind "${HOST}:${PORT}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  app:app

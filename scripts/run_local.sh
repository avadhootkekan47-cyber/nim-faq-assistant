#!/usr/bin/env bash
# scripts/run_local.sh
# ─────────────────────────────────────────────────────────────────────────────
# Starts the backend (and optionally opens the frontend in a browser).
# Run from the repo root: bash scripts/run_local.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "── Starting NIM FAQ Assistant (local) ───────────────────────────────────"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: open frontend/index.html in your browser"
echo "   API Docs: http://localhost:8000/docs"
echo ""

cd "$ROOT/backend"

# Activate venv if it exists
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Check .env
if [ ! -f ".env" ]; then
  echo "❌ backend/.env not found. Run: bash scripts/dev_setup.sh first."
  exit 1
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload

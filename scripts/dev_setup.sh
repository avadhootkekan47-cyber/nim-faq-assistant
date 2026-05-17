#!/usr/bin/env bash
# scripts/dev_setup.sh
# ─────────────────────────────────────────────────────────────────────────────
# One-time setup for local development.
# Run from the repo root: bash scripts/dev_setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "── NIM FAQ Assistant — Dev Setup ─────────────────────────────────────────"

# Check Python version
PYTHON=$(command -v python3 || command -v python)
PY_VER=$($PYTHON --version 2>&1 | awk '{print $2}')
echo "✔ Python: $PY_VER"

# Backend
echo ""
echo "── Setting up backend ────────────────────────────────────────────────────"
cd backend

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "✔ Created backend/.env from .env.example"
  echo "  ⚠️  Open backend/.env and fill in your NIM_API_KEY before running."
else
  echo "✔ backend/.env already exists — skipping."
fi

# Create virtual environment if not present
if [ ! -d ".venv" ]; then
  $PYTHON -m venv .venv
  echo "✔ Created .venv"
fi

source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -e ".[dev]"
echo "✔ Backend dependencies installed."

cd ..

echo ""
echo "── Done! ─────────────────────────────────────────────────────────────────"
echo ""
echo "Next steps:"
echo "  1. Edit backend/.env and set NIM_API_KEY"
echo "  2. Run:  bash scripts/run_local.sh"
echo ""

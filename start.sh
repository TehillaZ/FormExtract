#!/usr/bin/env bash
# Starts the whole app with one server: the database, the built interface, and the API. Then open http://localhost:8000
#   ./start.sh            start (builds the interface the first time)
#   ./start.sh --seed     also fill the database with the sample forms from saved model answers (no model needed)
#   ./start.sh --rebuild  rebuild the interface first
set -euo pipefail
cd "$(dirname "$0")"
seed=0; rebuild=0
for arg in "$@"; do case "$arg" in --seed) seed=1;; --rebuild) rebuild=1;; *) echo "unknown option $arg"; exit 2;; esac; done

echo "Database..."
docker compose up -d --wait db

if [ "$rebuild" = 1 ] || [ ! -f frontend/dist/index.html ]; then
  echo "Building the interface..."
  (cd frontend && npm install --no-audit --no-fund && npm run build)
fi

python=backend/.venv/Scripts/python.exe
[ -x "$python" ] || python=backend/.venv/bin/python
[ -x "$python" ] || { echo "Python environment not found. See the README, section Setup."; exit 1; }

if [ "$seed" = 1 ]; then
  echo "Seeding the sample forms from saved answers..."
  (cd backend && "../$python" scripts/seed_demo.py)
fi

echo "Open http://localhost:8000  (Ctrl+C to stop)"
cd backend && exec "../$python" -m uvicorn app.web:root --port 8000

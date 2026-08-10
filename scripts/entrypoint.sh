#!/bin/sh
set -eu

cd /app

if [ ! -f /app/data/healthcare.db ]; then
  echo "Seeding SQLite database..."
  python scripts/seed_db.py
else
  echo "SQLite database already present."
fi

# Single worker keeps in-memory conversation history coherent for the demo.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

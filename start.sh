#!/bin/bash
# Start the Incus Manager API

cd "$(dirname "$0")"

# Load .env if present (skip comment lines and empty lines)
if [ -f ".env" ]; then
    export $(grep -v '^\s*#' .env | grep -v '^\s*$' | xargs)
fi

HOST=${HOST:-127.0.0.1}
PORT=${PORT:-5000}
WORKERS=${WORKERS:-1}

# Auto-setup venv if not present
if [ ! -f ".venv/bin/uvicorn" ]; then
    echo "Virtual environment not found, running setup..."
    bash setup.sh
fi

echo "Starting Incus Manager API on http://$HOST:$PORT"
echo "  (secret prefix and docs URL will print on startup)"
echo ""

.venv/bin/uvicorn main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level info

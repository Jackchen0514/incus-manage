#!/bin/bash
# Start the Incus Manager API

HOST=${HOST:-0.0.0.0}
PORT=${PORT:-5000}
WORKERS=${WORKERS:-1}

cd "$(dirname "$0")"

# Auto-setup venv if not present
if [ ! -f ".venv/bin/uvicorn" ]; then
    echo "Virtual environment not found, running setup..."
    bash setup.sh
fi

echo "Starting Incus Manager API on http://$HOST:$PORT"
echo "  Docs:  http://$HOST:$PORT/docs"
echo "  ReDoc: http://$HOST:$PORT/redoc"
echo ""

.venv/bin/uvicorn main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level info

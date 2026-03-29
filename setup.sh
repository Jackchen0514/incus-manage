#!/bin/bash
# One-time setup: create virtualenv and install dependencies

set -e

cd "$(dirname "$0")"

echo "[1/3] Creating virtual environment..."
python3 -m venv .venv

echo "[2/3] Installing dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

echo "[3/3] Done!"
echo ""
echo "Start the API with:  ./start.sh"

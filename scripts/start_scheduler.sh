#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"

cd "$BACKEND_DIR"
source ../.venv/bin/activate 2>/dev/null || true

echo "Starting abstraction scheduler..."
python scheduler.py

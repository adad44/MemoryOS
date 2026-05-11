#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r backend/requirements.txt >/dev/null

export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"
exec .venv/bin/python -m enterprise.backend.app

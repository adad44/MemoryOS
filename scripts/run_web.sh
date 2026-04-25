#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${MEMORYOS_WEB_HOST:-127.0.0.1}"
PORT="${MEMORYOS_WEB_PORT:-5173}"
NPM="${MEMORYOS_NPM:-npm}"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

cd "$ROOT/web"

if [[ ! -d node_modules ]]; then
  echo "Missing web/node_modules. Run scripts/install_memoryos.sh first." >&2
  exit 1
fi

if [[ ! -d dist ]]; then
  "$NPM" run build
fi

exec "$NPM" run preview -- --host "$HOST" --port "$PORT"

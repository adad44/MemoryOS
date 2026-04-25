#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${MEMORYOS_OLLAMA_MODEL:-mistral}"
INSTALL_OLLAMA=1
PULL_MODEL=1
INSTALL_NATIVE=1
INSTALL_WEB=1
INSTALL_LAUNCH_AGENTS=1
INSTALL_SCHEDULER=1
INSTALL_EMBEDDINGS=0

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

usage() {
  cat <<USAGE
MemoryOS one-command installer for macOS.

Usage:
  scripts/install_memoryos.sh [options]

Options:
  --skip-ollama       Do not install/start Ollama.
  --skip-model-pull   Do not pull the local LLM model.
  --skip-native       Do not build/install the Swift daemon or menu bar app.
  --skip-web          Do not install/build/start the React web UI.
  --no-launch-agents  Install dependencies only; do not register services.
  --no-scheduler      Do not install the 6-hour Phase 7 abstraction scheduler.
  --with-embeddings   Install Torch, sentence-transformers, and FAISS extras.
  --model NAME        Ollama model to pull/use. Default: mistral.
  -h, --help          Show this help.

Examples:
  scripts/install_memoryos.sh
  scripts/install_memoryos.sh --skip-model-pull
  MEMORYOS_OLLAMA_MODEL=llama3.2 scripts/install_memoryos.sh --model llama3.2
USAGE
}

log() {
  printf "\n==> %s\n" "$1"
}

warn() {
  printf "warning: %s\n" "$1" >&2
}

die() {
  printf "error: %s\n" "$1" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

run() {
  printf "+ %s\n" "$*"
  "$@"
}

brew_install_if_missing() {
  local command_name="$1"
  local formula="$2"
  if have "$command_name"; then
    return
  fi
  log "Installing $formula"
  run brew install "$formula"
}

python_supports_memoryos() {
  "$1" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

python_can_create_venv() {
  local python_bin="$1"
  local tmp_dir
  tmp_dir="$(mktemp -d /tmp/memoryos-venv-check.XXXXXX)"
  if "$python_bin" -m venv "$tmp_dir" >/dev/null 2>&1 && "$tmp_dir/bin/python" -m pip --version >/dev/null 2>&1; then
    rm -rf "$tmp_dir"
    return 0
  fi
  rm -rf "$tmp_dir"
  return 1
}

select_python() {
  local candidates=()
  if [[ -n "${MEMORYOS_PYTHON:-}" ]]; then
    candidates+=("$MEMORYOS_PYTHON")
  fi
  candidates+=(
    /opt/homebrew/bin/python3.12
    /opt/homebrew/bin/python3.11
    /opt/homebrew/bin/python3.10
    /usr/local/bin/python3.12
    /usr/local/bin/python3.11
    /usr/local/bin/python3.10
    python3.12
    python3.11
    python3.10
    python3
  )

  local candidate
  local python_bin
  for candidate in "${candidates[@]}"; do
    python_bin="$(command -v "$candidate" 2>/dev/null || true)"
    if [[ -n "$python_bin" ]] && python_supports_memoryos "$python_bin" && python_can_create_venv "$python_bin"; then
      printf "%s\n" "$python_bin"
      return 0
    fi
  done
  return 1
}

wait_for_ollama() {
  local tries=0
  until curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; do
    tries=$((tries + 1))
    if (( tries > 40 )); then
      die "Ollama did not become ready on http://127.0.0.1:11434"
    fi
    sleep 1
  done
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local tries=0
  until curl -fsS --max-time 3 "$url" >/dev/null 2>&1; do
    tries=$((tries + 1))
    if (( tries > 60 )); then
      warn "$name did not respond at $url"
      return 1
    fi
    sleep 1
  done
  echo "$name is responding at $url"
}

model_is_available() {
  ollama list | awk -v model="$MODEL" 'NR > 1 && ($1 == model || $1 == model ":latest") {found = 1} END {exit !found}'
}

stop_existing_memoryos_agents() {
  local plist
  for plist in \
    "$HOME/Library/LaunchAgents/com.memoryos.backend.plist" \
    "$HOME/Library/LaunchAgents/com.memoryos.web.plist" \
    "$HOME/Library/LaunchAgents/com.memoryos.scheduler.plist" \
    "$HOME/Library/LaunchAgents/com.memoryos.daemon.plist" \
    "$HOME/Library/LaunchAgents/com.memoryos.menubar.plist"; do
    launchctl bootout "gui/$UID" "$plist" >/dev/null 2>&1 || true
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-ollama)
      INSTALL_OLLAMA=0
      PULL_MODEL=0
      shift
      ;;
    --skip-model-pull)
      PULL_MODEL=0
      shift
      ;;
    --skip-native)
      INSTALL_NATIVE=0
      shift
      ;;
    --skip-web)
      INSTALL_WEB=0
      shift
      ;;
    --no-launch-agents)
      INSTALL_LAUNCH_AGENTS=0
      shift
      ;;
    --no-scheduler)
      INSTALL_SCHEDULER=0
      shift
      ;;
    --with-embeddings)
      INSTALL_EMBEDDINGS=1
      shift
      ;;
    --model)
      [[ $# -ge 2 ]] || die "--model requires a value"
      MODEL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

[[ "$(uname -s)" == "Darwin" ]] || die "MemoryOS native install currently supports macOS only."
have brew || die "Homebrew is required. Install it from https://brew.sh, then rerun this script."

log "Installing MemoryOS from $ROOT"

log "Checking system tools"
PYTHON_BIN="$(select_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  log "Installing Python 3.12"
  run brew install python@3.12
  PYTHON_BIN="$(select_python || true)"
fi
[[ -n "$PYTHON_BIN" ]] || die "Could not find a Python 3.10+ interpreter that can create a venv."
echo "Using Python: $PYTHON_BIN"
if (( INSTALL_WEB == 1 )); then
  brew_install_if_missing node node
fi
if (( INSTALL_NATIVE == 1 )) && ! have swiftc; then
  xcode-select --install >/dev/null 2>&1 || true
  die "Swift compiler is missing. Finish installing Xcode Command Line Tools, then rerun this script. Use --skip-native to skip the daemon/menu bar build."
fi
if (( INSTALL_OLLAMA == 1 )); then
  brew_install_if_missing ollama ollama
fi

if (( INSTALL_LAUNCH_AGENTS == 1 )); then
  log "Stopping existing MemoryOS launch agents"
  stop_existing_memoryos_agents
fi

log "Creating Python virtual environment"
run "$PYTHON_BIN" -m venv --clear "$ROOT/.venv"
run "$ROOT/.venv/bin/python" -m pip install --upgrade pip
run "$ROOT/.venv/bin/python" -m pip install -r "$ROOT/backend/requirements.txt"
if (( INSTALL_EMBEDDINGS == 1 )); then
  log "Installing optional embedding/FAISS dependencies"
  run "$ROOT/.venv/bin/python" -m pip install -r "$ROOT/ml/requirements.txt"
fi
run "$ROOT/.venv/bin/python" "$ROOT/backend/db_phase7.py"

if (( INSTALL_WEB == 1 )); then
  log "Installing and building web UI"
  (
    cd "$ROOT/web"
    run npm install
    run npm run build
  )
fi

if (( INSTALL_NATIVE == 1 )); then
  log "Building native macOS components"
  run "$ROOT/scripts/build_daemon.sh"
  run "$ROOT/scripts/build_menubar.sh"
fi

if (( INSTALL_OLLAMA == 1 )); then
  log "Starting Ollama"
  run brew services start ollama
  wait_for_ollama

  if (( PULL_MODEL == 1 )); then
    if model_is_available; then
      echo "Ollama model already present: $MODEL"
    else
      log "Pulling Ollama model: $MODEL"
      warn "Cold model downloads can take longer than five minutes on slower networks."
      run ollama pull "$MODEL"
    fi
  fi
fi

if (( INSTALL_LAUNCH_AGENTS == 1 )); then
  log "Installing launch agents"
  run "$ROOT/scripts/install_backend_launch_agent.sh"
  if (( INSTALL_WEB == 1 )); then
    run "$ROOT/scripts/install_web_launch_agent.sh"
  fi
  if (( INSTALL_NATIVE == 1 )); then
    run env MEMORYOS_SKIP_BUILD=1 "$ROOT/scripts/install_daemon_launch_agent.sh"
    run env MEMORYOS_SKIP_BUILD=1 "$ROOT/scripts/install_menubar_launch_agent.sh"
  fi
  if (( INSTALL_SCHEDULER == 1 )); then
    if (( INSTALL_OLLAMA == 1 )) && model_is_available; then
      run "$ROOT/scripts/install_scheduler_launch_agent.sh"
    else
      warn "Skipping scheduler because Ollama/model is not available. Rerun without --skip-model-pull to enable Phase 7 scheduling."
    fi
  fi
fi

log "Verifying services"
if (( INSTALL_LAUNCH_AGENTS == 1 )); then
  launchctl print "gui/$UID/com.memoryos.backend" >/dev/null 2>&1 || warn "Backend launch agent is not loaded."
  wait_for_url "Backend" "http://127.0.0.1:8765/health" || true
  if (( INSTALL_WEB == 1 )); then
    launchctl print "gui/$UID/com.memoryos.web" >/dev/null 2>&1 || warn "Web launch agent is not loaded."
    wait_for_url "Web UI" "http://127.0.0.1:5173" || true
  fi
  if (( INSTALL_NATIVE == 1 )); then
    launchctl print "gui/$UID/com.memoryos.daemon" >/dev/null 2>&1 || warn "Daemon launch agent is not loaded."
    launchctl print "gui/$UID/com.memoryos.menubar" >/dev/null 2>&1 || warn "Menu bar launch agent is not loaded."
  fi
fi

if (( INSTALL_LAUNCH_AGENTS == 1 )); then
  BACKEND_STATUS="http://127.0.0.1:8765"
  WEB_STATUS="http://127.0.0.1:5173"
else
  BACKEND_STATUS="not started; run scripts/run_backend.sh"
  WEB_STATUS="not started; run scripts/run_web.sh"
fi
if (( INSTALL_WEB == 0 )); then
  WEB_STATUS="skipped"
fi

cat <<DONE

MemoryOS install complete.

Backend: $BACKEND_STATUS
Web UI:  $WEB_STATUS
Model:   $MODEL

Next:
1. Open the MemoryOS brain icon in the macOS menu bar.
2. Grant Accessibility and Full Disk Access when prompted.
3. Open the web UI and use Stats -> Reindex after captures arrive.

Logs are in:
$ROOT/.logs
DONE

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ORIGINAL_ARGS=("$@")
MODEL="${MEMORYOS_OLLAMA_MODEL:-mistral}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DATA_DIR="${MEMORYOS_DATA_DIR:-$DATA_HOME/memoryos}"
INSTALL_ROOT="${MEMORYOS_INSTALL_ROOT:-$DATA_DIR/app}"
DB_PATH="${MEMORYOS_DB:-$DATA_DIR/memoryos.db}"
INSTALL_OLLAMA=1
PULL_MODEL=1
INSTALL_WEB=1
INSTALL_CAPTURE_AGENT=1
INSTALL_SYSTEMD=1
INSTALL_SCHEDULER=1
INSTALL_EMBEDDINGS=0
OPEN_WEB_UI=1
COPY_TO_INSTALL_ROOT=1
INSTALL_SYSTEM_PACKAGES="${MEMORYOS_INSTALL_SYSTEM_PACKAGES:-1}"
INSTALL_OLLAMA_SCRIPT="${MEMORYOS_INSTALL_OLLAMA_SCRIPT:-1}"

usage() {
  cat <<USAGE
MemoryOS one-command installer for Linux.

This installs the FastAPI backend, React web UI, and Linux capture agent.
The Swift macOS daemon and menu bar app are not installed on Linux.

Usage:
  scripts/install_memoryos_linux.sh [options]

Options:
  --skip-ollama       Do not install/start Ollama.
  --skip-model-pull   Do not pull the local LLM model.
  --skip-web          Do not install/build/start the React web UI.
  --skip-capture      Do not install/start the Linux capture agent.
  --skip-native       Accepted for compatibility; Linux has no native macOS app.
  --no-systemd        Install dependencies only; do not register user services.
  --no-launch-agents  Alias for --no-systemd.
  --no-scheduler      Do not install the 6-hour abstraction scheduler service.
  --no-open           Do not open the web UI after install.
  --no-copy-install   Run services from the current checkout.
  --with-embeddings   Install Torch, sentence-transformers, and FAISS extras.
  --model NAME        Ollama model to pull/use. Default: mistral.
  -h, --help          Show this help.

Environment:
  MEMORYOS_INSTALL_SYSTEM_PACKAGES=0  Do not use sudo package managers.
  MEMORYOS_INSTALL_OLLAMA_SCRIPT=0    Do not run Ollama's Linux install script.
  MEMORYOS_INSTALL_ROOT=PATH          Install app copy here.
  MEMORYOS_DATA_DIR=PATH              Store database/settings here.
  MEMORYOS_DB=PATH                    Store SQLite database here.
  MEMORYOS_LINUX_WATCH_DIRS=PATHS     Colon-separated directories to scan.
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

as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  elif have sudo; then
    sudo "$@"
  else
    die "sudo is required to install missing system packages. Install them manually or rerun with MEMORYOS_INSTALL_SYSTEM_PACKAGES=0 after installing Python 3.10+, python venv, Node/npm, curl, and rsync."
  fi
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

node_supports_memoryos() {
  node - <<'JS' >/dev/null 2>&1
const major = Number.parseInt(process.versions.node.split(".")[0], 10);
process.exit(major >= 18 ? 0 : 1);
JS
}

select_python() {
  local candidates=()
  if [[ -n "${MEMORYOS_PYTHON:-}" ]]; then
    candidates+=("$MEMORYOS_PYTHON")
  fi
  candidates+=(python3.12 python3.11 python3.10 python3)

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

install_linux_packages() {
  if [[ "$INSTALL_SYSTEM_PACKAGES" != "1" ]]; then
    return
  fi

  log "Installing missing Linux system packages"
  if have apt-get; then
    run as_root apt-get update
    run as_root apt-get install -y python3 python3-venv python3-pip nodejs npm curl rsync xdotool
  elif have dnf; then
    run as_root dnf install -y python3 python3-pip nodejs npm curl rsync xdotool
  elif have pacman; then
    run as_root pacman -Sy --needed --noconfirm python python-pip nodejs npm curl rsync xdotool
  elif have zypper; then
    run as_root zypper install -y python3 python3-pip python3-virtualenv nodejs npm curl rsync xdotool
  else
    die "No supported package manager found. Install Python 3.10+ with venv, Node/npm, curl, and rsync, then rerun with MEMORYOS_INSTALL_SYSTEM_PACKAGES=0."
  fi
}

ensure_system_tools() {
  local needs_packages=0
  if ! select_python >/dev/null 2>&1; then
    needs_packages=1
  fi
  if (( INSTALL_WEB == 1 )) && (! have node || ! node_supports_memoryos || ! have npm); then
    needs_packages=1
  fi
  if ! have curl || ! have rsync; then
    needs_packages=1
  fi
  if (( INSTALL_CAPTURE_AGENT == 1 )) && (( INSTALL_SYSTEM_PACKAGES == 1 )) && ! have xdotool; then
    needs_packages=1
  fi

  if (( needs_packages == 1 )); then
    install_linux_packages
  fi

  select_python >/dev/null 2>&1 || die "Could not find Python 3.10+ with venv support."
  if (( INSTALL_WEB == 1 )); then
    have node || die "Node.js 18 or newer is required for the web UI."
    node_supports_memoryos || die "Node.js 18 or newer is required for the web UI. Install a newer Node.js, then rerun this script."
    have npm || die "npm is required for the web UI."
  fi
  have curl || die "curl is required."
  have rsync || die "rsync is required."
  if (( INSTALL_CAPTURE_AGENT == 1 )) && ! have xdotool; then
    warn "xdotool is not installed; Linux active-window capture will be disabled. File and browser capture still work."
  fi
}

copy_to_install_root_and_reexec() {
  if [[ "$ROOT" == "$INSTALL_ROOT" ]]; then
    return
  fi

  log "Copying app files to $INSTALL_ROOT"
  mkdir -p "$INSTALL_ROOT"
  rsync -a --delete \
    --exclude ".git/" \
    --exclude ".venv/" \
    --exclude ".logs/" \
    --exclude "web/node_modules/" \
    --exclude "web/dist/" \
    --exclude "daemon/.build/" \
    --exclude "menubar/.build/" \
    --exclude "menubar/dist/" \
    --exclude "presentation-workspace/node_modules/" \
    "$ROOT/" "$INSTALL_ROOT/"

  log "Continuing install from $INSTALL_ROOT"
  exec "$INSTALL_ROOT/scripts/install_memoryos_linux.sh" --no-copy-install "${ORIGINAL_ARGS[@]}"
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local tries=0
  until curl -fsS --max-time 3 "$url" >/dev/null 2>&1; do
    tries=$((tries + 1))
    if (( tries > 120 )); then
      warn "$name did not respond at $url"
      return 1
    fi
    sleep 1
  done
  echo "$name is responding at $url"
}

wait_for_ollama() {
  local tries=0
  until curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; do
    tries=$((tries + 1))
    if (( tries > 40 )); then
      return 1
    fi
    sleep 1
  done
}

install_ollama_if_missing() {
  if have ollama; then
    return
  fi
  if [[ "$INSTALL_OLLAMA_SCRIPT" != "1" ]]; then
    warn "Ollama is not installed. Install it from https://ollama.com/download/linux or rerun with --skip-ollama."
    return
  fi
  log "Installing Ollama"
  curl -fsSL https://ollama.com/install.sh | sh
}

start_ollama() {
  mkdir -p "$ROOT/.logs"
  if wait_for_ollama; then
    return
  fi
  if have ollama; then
    log "Starting Ollama"
    nohup ollama serve >"$ROOT/.logs/ollama.log" 2>&1 &
    if ! wait_for_ollama; then
      warn "Ollama did not become ready on http://127.0.0.1:11434. Check $ROOT/.logs/ollama.log."
    fi
  fi
}

model_is_available() {
  ollama list | awk -v model="$MODEL" 'NR > 1 && ($1 == model || $1 == model ":latest") {found = 1} END {exit !found}'
}

write_systemd_unit() {
  local name="$1"
  local description="$2"
  local command="$3"
  local unit_dir="$HOME/.config/systemd/user"
  mkdir -p "$unit_dir"
  cat > "$unit_dir/$name.service" <<UNIT
[Unit]
Description=$description
After=network.target

[Service]
Type=simple
WorkingDirectory=$ROOT
Environment=MEMORYOS_DATA_DIR=$DATA_DIR
Environment=MEMORYOS_DB=$DB_PATH
ExecStart=$command
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT
}

install_systemd_services() {
  have systemctl || {
    warn "systemctl is not available; skipping user services."
    return 1
  }
  systemctl --user status >/dev/null 2>&1 || {
    warn "systemd user manager is not available; skipping user services."
    return 1
  }

  log "Installing systemd user services"
  write_systemd_unit "memoryos-backend" "MemoryOS backend" "/usr/bin/env bash $ROOT/scripts/run_backend.sh"
  if (( INSTALL_WEB == 1 )); then
    write_systemd_unit "memoryos-web" "MemoryOS web UI" "/usr/bin/env bash $ROOT/scripts/run_web.sh"
  fi
  if (( INSTALL_SCHEDULER == 1 )); then
    write_systemd_unit "memoryos-scheduler" "MemoryOS abstraction scheduler" "/usr/bin/env bash $ROOT/scripts/start_scheduler.sh"
  fi
  if (( INSTALL_CAPTURE_AGENT == 1 )); then
    write_systemd_unit "memoryos-linux-capture" "MemoryOS Linux capture agent" "$ROOT/.venv/bin/python $ROOT/scripts/linux_capture_agent.py"
  fi

  run systemctl --user daemon-reload
  run systemctl --user enable --now memoryos-backend.service
  if (( INSTALL_WEB == 1 )); then
    run systemctl --user enable --now memoryos-web.service
  fi
  if (( INSTALL_SCHEDULER == 1 )); then
    run systemctl --user enable --now memoryos-scheduler.service
  fi
  if (( INSTALL_CAPTURE_AGENT == 1 )); then
    run systemctl --user enable --now memoryos-linux-capture.service
  fi
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
    --skip-web)
      INSTALL_WEB=0
      shift
      ;;
    --skip-capture)
      INSTALL_CAPTURE_AGENT=0
      shift
      ;;
    --skip-native)
      warn "--skip-native is a no-op on Linux; native macOS components are never installed."
      shift
      ;;
    --no-systemd|--no-launch-agents)
      INSTALL_SYSTEMD=0
      shift
      ;;
    --no-scheduler)
      INSTALL_SCHEDULER=0
      shift
      ;;
    --no-open)
      OPEN_WEB_UI=0
      shift
      ;;
    --no-copy-install)
      COPY_TO_INSTALL_ROOT=0
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

[[ "$(uname -s)" == "Linux" ]] || die "This installer is for Linux. Use scripts/install_memoryos.sh on macOS."

export MEMORYOS_DATA_DIR="$DATA_DIR"
export MEMORYOS_DB="$DB_PATH"

log "Installing MemoryOS for Linux from $ROOT"
ensure_system_tools

if (( COPY_TO_INSTALL_ROOT == 1 )); then
  copy_to_install_root_and_reexec
fi

mkdir -p "$DATA_DIR" "$ROOT/.logs"

log "Checking Python"
PYTHON_BIN="$(select_python || true)"
[[ -n "$PYTHON_BIN" ]] || die "Could not find a Python 3.10+ interpreter that can create a venv."
echo "Using Python: $PYTHON_BIN"

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

if (( INSTALL_OLLAMA == 1 )); then
  install_ollama_if_missing
  start_ollama
  if have ollama && wait_for_ollama && (( PULL_MODEL == 1 )); then
    if model_is_available; then
      echo "Ollama model already present: $MODEL"
    else
      log "Pulling Ollama model: $MODEL"
      warn "Cold model downloads can take longer than five minutes on slower networks."
      run ollama pull "$MODEL"
    fi
  fi
fi

SERVICES_STARTED=0
if (( INSTALL_SYSTEMD == 1 )); then
  if install_systemd_services; then
    SERVICES_STARTED=1
  fi
fi

if (( SERVICES_STARTED == 1 )); then
  log "Verifying services"
  wait_for_url "Backend" "http://127.0.0.1:8765/health" || true
  if (( INSTALL_WEB == 1 )); then
    wait_for_url "Web UI" "http://127.0.0.1:5173" || true
    if (( OPEN_WEB_UI == 1 )); then
      if have xdg-open; then
        xdg-open "http://127.0.0.1:5173" >/dev/null 2>&1 || warn "Could not open the web UI automatically."
      else
        warn "xdg-open is not installed; open http://127.0.0.1:5173 manually."
      fi
    fi
  fi
fi

if (( SERVICES_STARTED == 1 )); then
  BACKEND_STATUS="http://127.0.0.1:8765"
  WEB_STATUS="http://127.0.0.1:5173"
else
  BACKEND_STATUS="not started; run MEMORYOS_DB=\"$DB_PATH\" scripts/run_backend.sh"
  WEB_STATUS="not started; run cd web && npm run dev"
fi
CAPTURE_STATUS="not started; run MEMORYOS_DB=\"$DB_PATH\" .venv/bin/python scripts/linux_capture_agent.py"
if (( INSTALL_WEB == 0 )); then
  WEB_STATUS="skipped"
fi
if (( INSTALL_CAPTURE_AGENT == 0 )); then
  CAPTURE_STATUS="skipped"
elif (( SERVICES_STARTED == 1 )); then
  CAPTURE_STATUS="systemd user service: memoryos-linux-capture.service"
fi

cat <<DONE

MemoryOS Linux install complete.

Backend: $BACKEND_STATUS
Web UI:  $WEB_STATUS
Capture: $CAPTURE_STATUS
Model:   $MODEL
Data:    $DATA_DIR
DB:      $DB_PATH

Linux notes:
1. The backend, web UI, browser capture endpoint, Linux capture agent, search, storage controls, and user model are installed.
2. The Linux capture agent polls watched folders and uses xdotool for X11 active-window title capture when available.
3. Native macOS Accessibility capture and the menu bar app are macOS-only and are not installed.
4. If services were skipped, start the backend, web UI, and capture agent manually with the commands above.

Logs are in:
$ROOT/.logs
DONE

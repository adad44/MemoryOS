#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${MEMORYOS_REPO_URL:-https://github.com/adad44/MemoryOS.git}"
BRANCH="${MEMORYOS_BRANCH:-main}"
OS_NAME="$(uname -s)"

die() {
  printf "MemoryOS install error: %s\n" "$1" >&2
  exit 1
}

log() {
  printf "\n==> %s\n" "$1"
}

as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    die "sudo is required to install Git automatically. Install Git, then rerun this command."
  fi
}

install_git_linux() {
  [[ "${MEMORYOS_INSTALL_SYSTEM_PACKAGES:-1}" == "1" ]] || return
  log "Installing Git"
  if command -v apt-get >/dev/null 2>&1; then
    as_root apt-get update
    as_root apt-get install -y git
  elif command -v dnf >/dev/null 2>&1; then
    as_root dnf install -y git
  elif command -v pacman >/dev/null 2>&1; then
    as_root pacman -Sy --needed --noconfirm git
  elif command -v zypper >/dev/null 2>&1; then
    as_root zypper install -y git
  fi
}

case "$OS_NAME" in
  Darwin)
    SOURCE_DIR="${MEMORYOS_SOURCE_DIR:-$HOME/Library/Application Support/MemoryOS/source}"
    INSTALL_SCRIPT="scripts/install_memoryos.sh"
    ;;
  Linux)
    DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
    SOURCE_DIR="${MEMORYOS_SOURCE_DIR:-$DATA_HOME/memoryos/source}"
    INSTALL_SCRIPT="scripts/install_memoryos_linux.sh"
    ;;
  *)
    die "MemoryOS currently installs on macOS and Linux only."
    ;;
esac

if ! command -v git >/dev/null 2>&1 && [[ "$OS_NAME" == "Linux" ]]; then
  install_git_linux
fi
command -v git >/dev/null 2>&1 || die "git is required. Install Git, then rerun this command."

if [[ -d "$SOURCE_DIR/.git" ]]; then
  log "Updating MemoryOS source in $SOURCE_DIR"
  git -C "$SOURCE_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$SOURCE_DIR" checkout -q "$BRANCH"
  git -C "$SOURCE_DIR" reset --hard -q "origin/$BRANCH"
else
  log "Downloading MemoryOS to $SOURCE_DIR"
  mkdir -p "$(dirname "$SOURCE_DIR")"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$SOURCE_DIR"
fi

log "Running the MemoryOS installer"
exec "$SOURCE_DIR/$INSTALL_SCRIPT" "$@"

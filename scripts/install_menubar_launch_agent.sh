#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.memoryos.menubar.plist"
APP="$ROOT/menubar/dist/MemoryOS.app"
LOG_DIR="$ROOT/.logs"
DATA_DIR="${MEMORYOS_DATA_DIR:-$HOME/Library/Application Support/MemoryOS}"
DB_PATH="${MEMORYOS_DB:-$DATA_DIR/memoryos.db}"

if [[ "${MEMORYOS_SKIP_BUILD:-0}" != "1" || ! -x "$APP/Contents/MacOS/MemoryOS" ]]; then
  "$ROOT/scripts/build_menubar.sh"
fi
mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.memoryos.menubar</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MEMORYOS_DATA_DIR</key>
    <string>$DATA_DIR</string>
    <key>MEMORYOS_DB</key>
    <string>$DB_PATH</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/open</string>
    <string>-gj</string>
    <string>$APP</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/menubar.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/menubar.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl enable "gui/$UID/com.memoryos.menubar"

echo "Installed $PLIST"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.memoryos.web.plist"
LOG_DIR="$ROOT/.logs"
DATA_DIR="${MEMORYOS_DATA_DIR:-$HOME/Library/Application Support/MemoryOS}"
DB_PATH="${MEMORYOS_DB:-$DATA_DIR/memoryos.db}"
MODEL="${MEMORYOS_OLLAMA_MODEL:-mistral}"
PATH_VALUE="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.memoryos.web</string>
  <key>WorkingDirectory</key>
  <string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MEMORYOS_DATA_DIR</key>
    <string>$DATA_DIR</string>
    <key>MEMORYOS_DB</key>
    <string>$DB_PATH</string>
    <key>MEMORYOS_OLLAMA_MODEL</key>
    <string>$MODEL</string>
    <key>PATH</key>
    <string>$PATH_VALUE</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>bash</string>
    <string>$ROOT/scripts/run_web.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/web.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/web.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl enable "gui/$UID/com.memoryos.web"

echo "Installed $PLIST"

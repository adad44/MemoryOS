#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.memoryos.daemon.plist"
LOG_DIR="$ROOT/.logs"
DAEMON="$ROOT/daemon/.build/memoryos-daemon"

if [[ "${MEMORYOS_SKIP_BUILD:-0}" != "1" || ! -x "$DAEMON" ]]; then
  "$ROOT/scripts/build_daemon.sh"
fi
mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.memoryos.daemon</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DAEMON</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/daemon.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/daemon.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl enable "gui/$UID/com.memoryos.daemon"

echo "Installed $PLIST"

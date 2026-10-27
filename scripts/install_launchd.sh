#!/bin/bash
# Install a launchd service that keeps the MakGeography app running.
#
# Usage:  ./scripts/install_launchd.sh
#
# It reads the app location and password from the environment, so set those
# before running, or edit the generated plist afterwards.

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${MAKGEO_PYTHON:-/Users/davidhermes/.hermes/tools/python-3.14.7+20240901-darwin-arm64/bin/python3}"
PORT="${MAKGEO_PORT:-8781}"
LABEL="com.makgeo.app"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ -z "${MAKGEO_PASSWORD:-}" ]]; then
  echo "MAKGEO_PASSWORD is not set."
  echo "Export it first:  export MAKGEO_PASSWORD='your-password'"
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Python not found at $PYTHON"
  echo "Set MAKGEO_PYTHON to your interpreter, e.g."
  echo "  export MAKGEO_PYTHON=\$(command -v python3)"
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>-m</string>
    <string>uvicorn</string>
    <string>app.main:app</string>
    <string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>$PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$APP_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MAKGEO_PASSWORD</key><string>${MAKGEO_PASSWORD}</string>
    <key>MINIMAX_API_KEY</key><string>${MINIMAX_API_KEY:-}</string>
    <key>MINIMAX_BASE_URL</key><string>${MINIMAX_BASE_URL:-https://api.minimax.io/v1}</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/.hermes/logs/makgeo.out.log</string>
  <key>StandardErrorPath</key><string>$HOME/.hermes/logs/makgeo.err.log</string>
</dict>
</plist>
PLIST_EOF

mkdir -p "$HOME/.hermes/logs"

echo "Installing $LABEL..."
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

sleep 2
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/" | grep -q 200; then
  echo "OK — the app is serving on http://127.0.0.1:$PORT"
else
  echo "Started, but the health check did not return 200."
  echo "Check: tail -20 $HOME/.hermes/logs/makgeo.err.log"
fi

echo
echo "Logs:   $HOME/.hermes/logs/makgeo.err.log"
echo "Uninstall: launchctl unload $PLIST && rm $PLIST"

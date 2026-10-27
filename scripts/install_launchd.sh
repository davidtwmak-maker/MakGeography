#!/bin/bash
# Install the launchd jobs that run MakGeography on this Mac:
#
#   com.makgeo.app   - the FastAPI server, restarted if it dies
#   com.makgeo.news  - refreshes the geography news feed every hour
#
# Usage:  export MAKGEO_PASSWORD='your-password'
#         ./scripts/install_launchd.sh
#
# The API key is read from MINIMAX_API_KEY in the environment, or from
# ~/.hermes/.env. Neither the password nor the key is written into the repo.

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${MAKGEO_PORT:-8781}"
LOG_DIR="$HOME/.hermes/logs"
AGENT_DIR="$HOME/Library/LaunchAgents"

# Resolve the interpreter: override, else the Hermes toolchain (globbed, because
# the toolchain directory name contains a '+'), else whatever python3 is on PATH.
if [[ -n "${MAKGEO_PYTHON:-}" ]]; then
  PYTHON="$MAKGEO_PYTHON"
else
  PYTHON="$(ls -d "$HOME"/.hermes/tools/python-*/bin/python3 2>/dev/null | head -1 || true)"
  [[ -z "$PYTHON" ]] && PYTHON="$(command -v python3 || true)"
fi

if [[ -z "${MAKGEO_PASSWORD:-}" ]]; then
  echo "MAKGEO_PASSWORD is not set."
  echo "Export it first:  export MAKGEO_PASSWORD='your-password'"
  echo "(It is also read from ~/.hermes/.env if present.)"
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Python not found at $PYTHON"
  echo "Set MAKGEO_PYTHON to your interpreter, e.g."
  echo "  export MAKGEO_PYTHON=\$(command -v python3)"
  exit 1
fi

# The API key: environment first, then ~/.hermes/.env.
API_KEY="${MINIMAX_API_KEY:-}"
if [[ -z "$API_KEY" && -f "$HOME/.hermes/.env" ]]; then
  API_KEY="$(sed -n 's/^MINIMAX_API_KEY=//p' "$HOME/.hermes/.env" | tail -1 | tr -d "'\"" || true)"
fi
API_BASE="${MINIMAX_BASE_URL:-https://api.minimax.io/v1}"

mkdir -p "$LOG_DIR" "$AGENT_DIR" "$HOME/.hermes/cache/scratch" "$HOME/.hermes/scripts"

# --------------------------------------------------------------- app service
APP_PLIST="$AGENT_DIR/com.makgeo.app.plist"
cat > "$APP_PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.makgeo.app</string>
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
    <key>MAKGEO_PASSWORD</key><string>$MAKGEO_PASSWORD</string>
    <key>MINIMAX_API_KEY</key><string>$API_KEY</string>
    <key>MINIMAX_BASE_URL</key><string>$API_BASE</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG_DIR/makgeo.out.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/makgeo.err.log</string>
</dict>
</plist>
PLIST_EOF

# --------------------------------------------------------------- news refresh
NEWS_SCRIPT="$HOME/.hermes/scripts/makgeo_news_refresh.sh"
cat > "$NEWS_SCRIPT" <<'SCRIPT_EOF'
#!/bin/bash
# Refresh the MakGeography news feed. Fails soft: the previous news.json is
# left untouched if the collector fails.
set -uo pipefail

REPO="${MAKGEO_REPO:-__REPO__}"
PYTHON="${MAKGEO_PYTHON:-__PYTHON__}"
LOG="$HOME/.hermes/logs/makgeo-news.log"
LOCK="$HOME/.hermes/cache/scratch/makgeo-news.lock"

mkdir -p "$HOME/.hermes/logs" "$HOME/.hermes/cache/scratch"
log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# Concurrency guard: O_CREAT|O_EXCL, stale locks reaped by age.
if ! ( set -o noclobber; : > "$LOCK" ) 2>/dev/null; then
  if [ -f "$LOCK" ] && [ "$(find "$LOCK" -mmin +30 2>/dev/null)" ]; then
    log "stale lock found, removing"
    rm -f "$LOCK"
    ( set -o noclobber; : > "$LOCK" ) 2>/dev/null || { log "another run is in progress, exiting"; exit 0; }
  else
    log "another run is in progress, exiting"
    exit 0
  fi
fi
trap 'rm -f "$LOCK"' EXIT

if [ ! -x "$PYTHON" ]; then
  log "FAIL: python not found at $PYTHON"
  exit 1
fi

cd "$REPO" || { log "FAIL: repo not found at $REPO"; exit 1; }

log "starting news refresh"
if "$PYTHON" scripts/collect_news.py >> "$LOG" 2>&1; then
  log "OK: news refreshed"
else
  log "FAIL: collector returned non-zero (previous news.json left in place)"
  exit 1
fi
SCRIPT_EOF

sed -i '' "s|__REPO__|$APP_DIR|g; s|__PYTHON__|$PYTHON|g" "$NEWS_SCRIPT"
chmod +x "$NEWS_SCRIPT"

NEWS_PLIST="$AGENT_DIR/com.makgeo.news.plist"
cat > "$NEWS_PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.makgeo.news</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$NEWS_SCRIPT</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MAKGEO_REPO</key><string>$APP_DIR</string>
    <key>MAKGEO_PYTHON</key><string>$PYTHON</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>3600</integer>
</dict>
</plist>
PLIST_EOF

# ------------------------------------------------------------------- install
for P in "$APP_PLIST" "$NEWS_PLIST"; do
  plutil -lint "$P" >/dev/null || { echo "Plist is malformed: $P"; exit 1; }
done

echo "Installing com.makgeo.app..."
launchctl bootout "gui/$(id -u)/com.makgeo.app" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$APP_PLIST"

echo "Installing com.makgeo.news..."
launchctl bootout "gui/$(id -u)/com.makgeo.news" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$NEWS_PLIST"

sleep 3
echo
for LABEL in com.makgeo.app com.makgeo.news; do
  printf '%-18s %s\n' "$LABEL" \
    "$(launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | grep -m1 'state =' || echo 'not loaded')"
done

if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/" | grep -q 200; then
  echo
  echo "OK - the app is serving on http://127.0.0.1:$PORT"
else
  echo
  echo "The app started, but the health check did not return 200."
  echo "Check: tail -20 $LOG_DIR/makgeo.err.log"
fi

echo
echo "App logs:  $LOG_DIR/makgeo.err.log"
echo "News logs: $LOG_DIR/makgeo-news.log"
echo "Uninstall: launchctl bootout gui/\$(id -u)/com.makgeo.app; \\"
echo "           launchctl bootout gui/\$(id -u)/com.makgeo.news; \\"
echo "           rm $APP_PLIST $NEWS_PLIST"

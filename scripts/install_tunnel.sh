#!/bin/bash
# Keep a public SSH tunnel to the MakGeography app open.
#
# Usage: ./scripts/install_tunnel.sh
#
# Creates com.makgeo.tunnel, an SSH reverse tunnel to serveo.net that forwards
# the public URL to 127.0.0.1:8781. The assigned URL is written to
# ~/.hermes/logs/makgeo-url.txt so it can be read without digging in logs.
#
# A free serveo.net URL changes if the tunnel restarts. For a permanent URL,
# register an SSH key with serveo and request a subdomain, or use a named
# Cloudflare tunnel (see docs/deployment.md).
set -uo pipefail

PORT="${MAKGEO_PORT:-8781}"
LOG_DIR="$HOME/.hermes/logs"
PLIST="$HOME/Library/LaunchAgents/com.makgeo.tunnel.plist"
URL_FILE="$LOG_DIR/makgeo-url.txt"

mkdir -p "$LOG_DIR"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.makgeo.tunnel</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/ssh</string>
    <string>-N</string>
    <string>-o</string><string>StrictHostKeyChecking=no</string>
    <string>-o</string><string>UserKnownHostsFile=/dev/null</string>
    <string>-o</string><string>ServerAliveInterval=30</string>
    <string>-o</string><string>ExitOnForwardFailure=yes</string>
    <string>-R</string><string>80:localhost:__PORT__</string>
    <string>serveo.net</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>__LOG_DIR__/makgeo-tunnel.log</string>
  <key>StandardErrorPath</key><string>__LOG_DIR__/makgeo-tunnel.log</string>
</dict>
</plist>
PLIST_EOF

sed -i '' "s|__PORT__|$PORT|g; s|__LOG_DIR__|$LOG_DIR|g" "$PLIST"

if ! plutil -lint "$PLIST" >/dev/null; then
  echo "Plist is malformed."
  exit 1
fi

echo "Installing com.makgeo.tunnel..."
launchctl bootout "gui/$(id -u)/com.makgeo.tunnel" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

# Serveo assigns a URL on connect; it occasionally refuses (rate limiting when
# the tunnel is restarted repeatedly), so fall back to localtunnel.
wait_for_url() {
  local pattern="$1" logfile="$2"
  for i in $(seq 1 20); do
    sleep 2
    url="$(grep -oE "$pattern" "$logfile" 2>/dev/null | tail -1)"
    [ -n "$url" ] && { echo "$url"; return 0; }
  done
  return 1
}

echo "Waiting for the URL..."
url="$(wait_for_url 'https://[a-zA-Z0-9.-]+\.serveousercontent\.com' "$LOG_DIR/makgeo-tunnel.log")"

if [ -z "$url" ]; then
  echo "Serveo did not assign a URL (it rate-limits restarts). Falling back to localtunnel."
  launchctl bootout "gui/$(id -u)/com.makgeo.tunnel" 2>/dev/null || true
  command -v npx >/dev/null 2>&1 || {
    echo "npx is not available. Install Node, or use a named Cloudflare tunnel."
    exit 1
  }
  cat > "$HOME/.hermes/scripts/makgeo_tunnel_run.sh" <<'RUN_EOF'
#!/bin/bash
# localtunnel forward for MakGeography. localtunnel shows a one-time
# interstitial asking for the visitor's public IP; it is dismissable.
#
# The URL changes every time the tunnel restarts, so write the current one to
# a file that survives the restart. Otherwise a restarted tunnel leaves a dead
# URL in the student's hands.
set -uo pipefail
PORT="__PORT__"
URL_FILE="__URL_FILE__"
LOG="$HOME/.hermes/logs/makgeo-tunnel.log"

mkdir -p "$HOME/.hermes/logs"
: > "$LOG"
npx --yes localtunnel --port "$PORT" --local-host 127.0.0.1 2>&1 | tee -a "$LOG" &
LT_PID=$!

# Watch the log for the assigned URL and record it.
while kill -0 "$LT_PID" 2>/dev/null; do
  url="$(grep -oE 'https://[a-zA-Z0-9-]+\.loca\.lt' "$LOG" 2>/dev/null | tail -1)"
  if [ -n "$url" ]; then
    echo "$url" > "$URL_FILE"
  fi
  sleep 3
done

# localtunnel exited - let launchd restart us.
wait "$LT_PID"
exit $?
RUN_EOF
  sed -i '' "s|__PORT__|$PORT|g; s|__URL_FILE__|$URL_FILE|g" "$HOME/.hermes/scripts/makgeo_tunnel_run.sh"
  chmod +x "$HOME/.hermes/scripts/makgeo_tunnel_run.sh"

  cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.makgeo.tunnel</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>__HOME__/.hermes/scripts/makgeo_tunnel_run.sh</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>__PATH__</string>
    <key>HOME</key><string>__HOME__</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>__LOG_DIR__/makgeo-tunnel.log</string>
  <key>StandardErrorPath</key><string>__LOG_DIR__/makgeo-tunnel.log</string>
</dict>
</plist>
PLIST_EOF
  # The path can contain & and /, so escape them for the sed replacement and
  # for the XML itself.
  sed_escape() { printf '%s' "$1" | sed -e 's/[&|\\]/\\&/g'; }
  HOME_ESC="$(sed_escape "$HOME")"
  LOG_ESC="$(sed_escape "$LOG_DIR")"
  # A fixed PATH keeps the XML simple and is enough for ssh and npx.
  NODE_BIN="$(dirname "$(command -v npx 2>/dev/null || echo /usr/bin/false)")"
  PATH_ESC="$(sed_escape "$NODE_BIN:/usr/bin:/bin:/usr/sbin:/sbin")"
  sed -i '' "s|__HOME__|$HOME_ESC|g; s|__LOG_DIR__|$LOG_ESC|g; s|__PATH__|$PATH_ESC|g" "$PLIST"
  plutil -lint "$PLIST" >/dev/null || { echo "Plist malformed"; exit 1; }
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  url="$(wait_for_url 'https://[a-zA-Z0-9-]+\.loca\.lt' "$LOG_DIR/makgeo-tunnel.log")"
fi

if [ -z "$url" ]; then
  echo "No URL assigned. Check: tail -20 $LOG_DIR/makgeo-tunnel.log"
  exit 1
fi

echo "$url" > "$URL_FILE"
echo
echo "Public URL: $url"
echo "Read it later with: cat $URL_FILE"
echo
if curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$url/" | grep -q 200; then
  echo "OK - the site is answering on that URL."
else
  echo "The tunnel is up but the health check did not return 200."
fi

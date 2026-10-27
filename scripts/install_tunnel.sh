#!/bin/bash
# Keep a public tunnel to the MakGeography app open.
#
# Usage: ./scripts/install_tunnel.sh
#
# Creates com.makgeo.tunnel, which serves the app on a public HTTPS URL.
# The assigned URL is written to ~/.hermes/logs/makgeo-url.txt so it can be
# read without digging in logs.
#
# The default is a Cloudflare quick tunnel (cloudflared). It is used in
# preference to localtunnel because localtunnel shows a one-time
# interstitial asking the visitor for their public IP before the site
# appears - a quick tunnel goes straight to the site.
#
# A quick-tunnel URL changes when the tunnel restarts. For a permanent URL,
# set up a named Cloudflare tunnel with your own domain (see
# docs/deployment.md).
set -uo pipefail

PORT="${MAKGEO_PORT:-8781}"
LOG_DIR="$HOME/.hermes/logs"
PLIST="$HOME/Library/LaunchAgents/com.makgeo.tunnel.plist"
URL_FILE="$LOG_DIR/makgeo-url.txt"
RUNNER="$HOME/.hermes/scripts/makgeo_tunnel_run.sh"
TOOLS_BIN="$HOME/.hermes/tools/bin"
CLOUDFLARED="$TOOLS_BIN/cloudflared"

mkdir -p "$LOG_DIR" "$TOOLS_BIN" "$HOME/.hermes/scripts"

wait_for_url() {
  local pattern="$1" logfile="$2"
  for _ in $(seq 1 25); do
    sleep 2
    url="$(grep -oE "$pattern" "$logfile" 2>/dev/null | tail -1)"
    [ -n "$url" ] && { echo "$url"; return 0; }
  done
  return 1
}

# The path can contain & and /, so escape them for the sed replacement and
# for the XML itself.
sed_escape() { printf '%s' "$1" | sed -e 's/[&|\\]/\\&/g'; }
HOME_ESC="$(sed_escape "$HOME")"
LOG_ESC="$(sed_escape "$LOG_DIR")"
PATH_ESC="$(sed_escape "/usr/bin:/bin:/usr/sbin:/sbin")"

write_plist() {
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
  sed -i '' "s|__HOME__|$HOME_ESC|g; s|__LOG_DIR__|$LOG_ESC|g; s|__PATH__|$PATH_ESC|g" "$PLIST"
  plutil -lint "$PLIST" >/dev/null || { echo "Plist malformed"; exit 1; }
}

install_cloudflared() {
  local url="$1"
  cat > "$RUNNER" <<'RUN_EOF'
#!/bin/bash
# Public tunnel for MakGeography, using Cloudflare's quick tunnel.
#
# Why cloudflared rather than localtunnel: localtunnel serves a one-time
# interstitial asking the visitor for their public IP before the site
# appears. A quick tunnel goes straight to the site - no interstitial, and
# it is a real HTTPS URL.
#
# The URL changes every time the tunnel restarts, so the current one is
# written to a file that survives the restart. Otherwise a restarted tunnel
# leaves a dead URL in the student's hands.
set -uo pipefail
PORT="__PORT__"
URL_FILE="__URL_FILE__"
LOG="$HOME/.hermes/logs/makgeo-tunnel.log"
CLOUDFLARED="$HOME/.hermes/tools/bin/cloudflared"

mkdir -p "$HOME/.hermes/logs" "$HOME/.hermes/tools/bin"

if [ ! -x "$CLOUDFLARED" ]; then
  echo "cloudflared is not installed at $CLOUDFLARED" | tee -a "$LOG"
  exit 1
fi

: > "$LOG"

"$CLOUDFLARED" tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" \
  2>&1 | tee -a "$LOG" &
CF_PID=$!

# Watch the log for the assigned URL and record it.
while kill -0 "$CF_PID" 2>/dev/null; do
  url="$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | tail -1)"
  if [ -n "$url" ]; then
    echo "$url" > "$URL_FILE"
  fi
  sleep 3
done

# cloudflared exited - let launchd restart us.
wait "$CF_PID"
exit $?
RUN_EOF
  sed -i '' "s|__PORT__|$PORT|g; s|__URL_FILE__|$URL_FILE|g" "$RUNNER"
  chmod +x "$RUNNER"
  write_plist
  launchctl bootout "gui/$(id -u)/com.makgeo.tunnel" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  wait_for_url "$url" "$LOG_DIR/makgeo-tunnel.log"
}

install_localtunnel() {
  cat > "$RUNNER" <<'RUN_EOF'
#!/bin/bash
# localtunnel forward for MakGeography. This is the FALLBACK: localtunnel
# shows a one-time interstitial asking the visitor for their public IP
# before the site appears.
set -uo pipefail
PORT="__PORT__"
URL_FILE="__URL_FILE__"
LOG="$HOME/.hermes/logs/makgeo-tunnel.log"

mkdir -p "$HOME/.hermes/logs"
: > "$LOG"
npx --yes localtunnel --port "$PORT" --local-host 127.0.0.1 2>&1 | tee -a "$LOG" &
LT_PID=$!

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
  sed -i '' "s|__PORT__|$PORT|g; s|__URL_FILE__|$URL_FILE|g" "$RUNNER"
  chmod +x "$RUNNER"
  write_plist
  launchctl bootout "gui/$(id -u)/com.makgeo.tunnel" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  wait_for_url 'https://[a-zA-Z0-9-]+\.loca\.lt' "$LOG_DIR/makgeo-tunnel.log"
}

echo "Installing com.makgeo.tunnel..."

# Fetch cloudflared if it is not already there.
if [ ! -x "$CLOUDFLARED" ]; then
  echo "Fetching cloudflared..."
  ARCH="$(uname -m)"
  case "$ARCH" in
    arm64) ASSET="cloudflared-darwin-arm64.tgz" ;;
    *)     ASSET="cloudflared-darwin-amd64.tgz" ;;
  esac
  TAG="$(curl -s --max-time 60 https://api.github.com/repos/cloudflare/cloudflared/releases/latest \
    | grep -m1 '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')"
  if [ -n "$TAG" ]; then
    tmp="$(mktemp -d)"
    if curl -sL --max-time 300 -o "$tmp/cf.tgz" \
        "https://github.com/cloudflare/cloudflared/releases/download/$TAG/$ASSET" \
       && tar xzf "$tmp/cf.tgz" -C "$tmp" 2>/dev/null; then
      mv "$tmp/cloudflared" "$CLOUDFLARED"
      chmod +x "$CLOUDFLARED"
      rm -rf "$tmp"
    fi
  fi
fi

if [ -x "$CLOUDFLARED" ]; then
  echo "Using a Cloudflare quick tunnel (no interstitial)."
  url="$(install_cloudflared 'https://[a-zA-Z0-9-]+\.trycloudflare\.com')"
else
  echo "cloudflared is unavailable. Falling back to localtunnel."
  command -v npx >/dev/null 2>&1 || {
    echo "npx is not available either. Install Node, or download cloudflared."
    exit 1
  }
  url="$(install_localtunnel)"
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

# The tunnel registers the hostname just after it prints the URL, and the
# local resolver can hold a negative answer for a moment afterwards. Give
# the name a few chances to start working before declaring failure.
ok=0
for _ in $(seq 1 8); do
  if curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$url/" | grep -q 200; then
    ok=1
    break
  fi
  sleep 5
done

if [ "$ok" = "1" ]; then
  echo "OK - the site is answering on that URL."
else
  echo "The tunnel is up but the health check did not return 200."
  echo "It may just need a moment - check again with:"
  echo "  curl -sI $url/ | head -1"
fi

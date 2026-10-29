#!/bin/bash
# Keep a public tunnel to the MakGeography app open.
#
# Usage: ./scripts/install_tunnel.sh
#
# Creates com.makgeo.tunnel, which serves the app on a public HTTPS URL.
# The assigned URL is written to ~/.hermes/logs/makgeo-url.txt so it can be
# read without digging in logs.
#
# Three ways to publish the site, in order of preference:
#
#   1. Serveo, over SSH. The subdomain is reserved against the SSH key, so
#      the address is the same every time the tunnel restarts:
#
#          https://<subdomain>.serveousercontent.com
#
#      This is what the site uses. A student who saved the address has it
#      still working next week.
#
#   2. A Cloudflare quick tunnel. The hostname is random and changes on
#      every restart. It needs no account, so it is the fallback when
#      there is no Serveo key.
#
#   3. localtunnel. The last resort: it shows the visitor a one-time
#      interstitial asking for their public IP before the site appears.
#
# To use Serveo, the key at ~/.ssh/serveo_rsa must exist and its
# fingerprint must be registered to a Serveo account. The account password
# is not needed here and is never written into the script or the plist.
set -uo pipefail

PORT="${MAKGEO_PORT:-8781}"
LOG_DIR="$HOME/.hermes/logs"
PLIST="$HOME/Library/LaunchAgents/com.makgeo.tunnel.plist"
PLIST_CF="$HOME/Library/LaunchAgents/com.makgeo.tunnel.cf.plist"
URL_FILE="$LOG_DIR/makgeo-url.txt"
URL_FILE_CF="$LOG_DIR/makgeo-url-cf.txt"
RUNNER="$HOME/.hermes/scripts/makgeo_tunnel_run.sh"
RUNNER_CF="$HOME/.hermes/scripts/makgeo_tunnel_cf_run.sh"
TOOLS_BIN="$HOME/.hermes/tools/bin"
CLOUDFLARED="$TOOLS_BIN/cloudflared"
SERVEO_KEY="${MAKGEO_SERVEO_KEY:-$HOME/.ssh/serveo_rsa}"
SUBDOMAIN="${MAKGEO_SUBDOMAIN:-makgeography}"

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
    <key>MAKGEO_PORT</key><string>__PORT__</string>
    <key>MAKGEO_SUBDOMAIN</key><string>__SUBDOMAIN__</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>__LOG_DIR__/makgeo-tunnel.log</string>
  <key>StandardErrorPath</key><string>__LOG_DIR__/makgeo-tunnel.log</string>
</dict>
</plist>
PLIST_EOF
  sed -i '' "s|__HOME__|$HOME_ESC|g; s|__LOG_DIR__|$LOG_ESC|g; s|__PATH__|$PATH_ESC|g; s|__PORT__|$PORT|g; s|__SUBDOMAIN__|$SUBDOMAIN|g" "$PLIST"
  plutil -lint "$PLIST" >/dev/null || { echo "Plist malformed"; exit 1; }
}

# The Cloudflare tunnel gets its own job, so it can run alongside the
# Serveo one. Its address is the clean one; Serveo's is the permanent one.
write_plist_cf() {
  cat > "$PLIST_CF" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.makgeo.tunnel.cf</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>__HOME__/.hermes/scripts/makgeo_tunnel_cf_run.sh</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>__PATH__</string>
    <key>HOME</key><string>__HOME__</string>
    <key>MAKGEO_PORT</key><string>__PORT__</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>__LOG_DIR__/makgeo-tunnel-cf.log</string>
  <key>StandardErrorPath</key><string>__LOG_DIR__/makgeo-tunnel-cf.log</string>
</dict>
</plist>
PLIST_EOF
  sed -i '' "s|__HOME__|$HOME_ESC|g; s|__LOG_DIR__|$LOG_ESC|g; s|__PATH__|$PATH_ESC|g; s|__PORT__|$PORT|g" "$PLIST_CF"
  plutil -lint "$PLIST_CF" >/dev/null || { echo "Plist malformed"; exit 1; }
}

# The Serveo runner. The subdomain is reserved against the key, so the
# address survives a restart.
install_serveo() {
  cat > "$RUNNER" <<'RUN_EOF'
#!/bin/bash
# Public tunnel for MakGeography, using Serveo over SSH.
#
# The subdomain is reserved against the registered SSH key, so the
# address is the same every time the tunnel restarts:
#
#     https://<subdomain>.serveousercontent.com
#
# The key is ~/.ssh/serveo_rsa (override with MAKGEO_SERVEO_KEY). The
# account password is not needed and is never written into this script.
set -uo pipefail
PORT="${MAKGEO_PORT:-8781}"
URL_FILE="$HOME/.hermes/logs/makgeo-url.txt"
LOG="$HOME/.hermes/logs/makgeo-tunnel.log"
KEY="${MAKGEO_SERVEO_KEY:-$HOME/.ssh/serveo_rsa}"
SUBDOMAIN="${MAKGEO_SUBDOMAIN:-makgeography}"

mkdir -p "$HOME/.hermes/logs"

if [ ! -f "$KEY" ]; then
  echo "The Serveo SSH key is missing at $KEY"
  exit 1
fi
chmod 600 "$KEY" 2>/dev/null || true

if ! curl -s -o /dev/null --max-time 10 "http://127.0.0.1:$PORT/"; then
  echo "The app is not answering on port $PORT"
  exit 1
fi

# launchd already sends stdout and stderr to the tunnel log, so these
# messages are written with a plain echo. Using tee as well would write
# every line twice, and the URL watcher below greps that file.
echo "starting the Serveo tunnel for https://${SUBDOMAIN}.serveousercontent.com"

ssh -i "$KEY" \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -R "${SUBDOMAIN}:80:127.0.0.1:${PORT}" \
  serveo@serveo.net 2>&1 &
SSH_PID=$!

# Keep the URL file current.
#
# The address written is the one a student should open. Serveo shows a
# warning page to real browsers on an HTTP tunnel, and that page is
# served by Serveo's edge before the request reaches the app - so the
# app cannot redirect around it.
#
# Serveo does skip the page for a request that carries
# "serveo-skip-browser-warning", and answers it with a 302 that sets
# the cookie for a year. So the URL written here carries that
# parameter: a student's first visit sets the cookie and lands on the
# real site, and every visit after that is clean.
while kill -0 "$SSH_PID" 2>/dev/null; do
  url="$(grep -oE 'https://[a-zA-Z0-9-]+\.serveousercontent\.com' "$LOG" 2>/dev/null | tail -1)"
  if [ -n "$url" ]; then
    echo "${url}/?serveo-skip-browser-warning=true" > "$URL_FILE"
  fi
  sleep 3
done

# ssh exited - let launchd restart us.
wait "$SSH_PID"
exit $?
RUN_EOF
  chmod +x "$RUNNER"
  write_plist
  launchctl bootout "gui/$(id -u)/com.makgeo.tunnel" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  wait_for_url 'https://[a-zA-Z0-9-]+\.serveousercontent\.com' "$LOG_DIR/makgeo-tunnel.log"
}

install_cloudflared() {
  cat > "$RUNNER_CF" <<'RUN_EOF'
#!/bin/bash
# Public tunnel for MakGeography, using Cloudflare's quick tunnel.
#
# This one runs ALONGSIDE the Serveo tunnel, not instead of it.
#
# Serveo serves a warning interstitial to real browsers on an HTTP
# tunnel: a student opening the site saw "Serveo - Warning" and a
# "Continue to Site" button instead of the site. The interstitial is
# served by Serveo's edge before the request reaches the app, so the app
# cannot redirect around it, and a fetch() to any path gets the same
# HTML page - which is what broke the Ask panel.
#
# The Cloudflare quick tunnel serves the site directly, with no
# interstitial. The hostname is random and changes on every restart, so
# the current one is written to a file that survives the restart -
# otherwise a restarted tunnel leaves a dead URL in the student's hands.
#
# The Serveo address stays the permanent one; this is the clean one to
# hand to a student who needs the site right now.
set -uo pipefail
PORT="${MAKGEO_PORT:-8781}"
URL_FILE="$HOME/.hermes/logs/makgeo-url-cf.txt"
LOG="$HOME/.hermes/logs/makgeo-tunnel-cf.log"
CLOUDFLARED="$HOME/.hermes/tools/bin/cloudflared"

mkdir -p "$HOME/.hermes/logs" "$HOME/.hermes/tools/bin"

if [ ! -x "$CLOUDFLARED" ]; then
  echo "cloudflared is not installed at $CLOUDFLARED" | tee -a "$LOG"
  exit 1
fi

# launchd already captures stdout and stderr to the tunnel log, so these
# messages are written with a plain echo. Using tee as well would write
# every line twice, and the URL watcher below greps that file.
echo "starting the Cloudflare tunnel for the MakGeography app"

# The metrics port.
#
# cloudflared listens on 127.0.0.1:20242 by default. Two tunnels on one
# machine - the launchd one and one started by hand to test something -
# collide on that port, and the loser gets a hostname it never owns.
# Its registration is then rejected ("Tunnel not found") and it retries
# forever while the process stays alive, so launchd never notices and the
# address is dead. Each tunnel gets its own port.
METRICS_PORT="${MAKGEO_CF_METRICS_PORT:-20242}"

"$CLOUDFLARED" tunnel --no-autoupdate \
  --metrics "127.0.0.1:${METRICS_PORT}" \
  --url "http://127.0.0.1:$PORT" \
  2>&1 &
CF_PID=$!

# The URL for THIS episode of the tunnel.
#
# It is read from the log from the point where this run started, not from
# the whole file. A quick tunnel gets a new hostname every time, so the
# last hostname in the log belongs to the PREVIOUS episode - reading it
# would hand out a dead address and the watchdog would then restart the
# tunnel in a loop, never reaching a working one.
LOG_START="$(wc -c < "$LOG" 2>/dev/null || echo 0)"

while kill -0 "$CF_PID" 2>/dev/null; do
  url="$(tail -c "+$((LOG_START + 1))" "$LOG" 2>/dev/null \
    | grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | tail -1)"
  if [ -n "$url" ]; then
    echo "$url" > "$URL_FILE"

    # The watchdog matters: cloudflared can lose its tunnel registration
    # ("Unauthorized: Tunnel not found") and then sit there retrying
    # forever. The process stays alive, so launchd never notices, and the
    # hostname stops resolving - the tunnel looks up in the process table
    # and the address is dead. So the URL is checked, not just the process.
    if [ $((SECONDS % 300)) -lt 4 ]; then
      code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url" 2>/dev/null)"
      # curl prints 000 when it cannot reach the host; treat anything
      # that is not 200 as a dead tunnel.
      if [ "$code" != "200" ]; then
        echo "the Cloudflare tunnel at $url stopped answering (HTTP $code); restarting it"
        # Clear the URL file first. Otherwise the next start reads this
        # same dead hostname from the log, finds it is not answering, and
        # restarts again - a loop that never reaches a working tunnel.
        : > "$URL_FILE"
        kill "$CF_PID" 2>/dev/null
        break
      fi
    fi
  fi
  sleep 3
done

# cloudflared exited - let launchd restart us.
wait "$CF_PID"
exit $?
RUN_EOF
  chmod +x "$RUNNER_CF"
  write_plist_cf
  launchctl bootout "gui/$(id -u)/com.makgeo.tunnel.cf" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST_CF" 2>/dev/null \
    || launchctl load -w "$PLIST_CF"
  wait_for_url 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG_DIR/makgeo-tunnel-cf.log"
}

install_cloudflared_as_fallback() {
  cat > "$RUNNER" <<'RUN_EOF'
#!/bin/bash
# Public tunnel for MakGeography, using Cloudflare's quick tunnel.
#
# The fallback when there is no Serveo key. The hostname is random and
# changes on every restart, so the current one is written to a file that
# survives the restart - otherwise a restarted tunnel leaves a dead URL
# in the student's hands.
set -uo pipefail
PORT="${MAKGEO_PORT:-8781}"
URL_FILE="$HOME/.hermes/logs/makgeo-url.txt"
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

# The URL for THIS episode of the tunnel. The log was emptied above, so
# everything in it belongs to this run - but the URL is still read from
# the point where this run started, so a later append of an old hostname
# cannot make the watchdog restart a healthy tunnel.
LOG_START="$(wc -c < "$LOG" 2>/dev/null || echo 0)"

while kill -0 "$CF_PID" 2>/dev/null; do
  url="$(tail -c "+$((LOG_START + 1))" "$LOG" 2>/dev/null \
    | grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | tail -1)"
  if [ -n "$url" ]; then
    echo "$url" > "$URL_FILE"

    # The watchdog matters: cloudflared can lose its tunnel registration
    # ("Unauthorized: Tunnel not found") and then sit there retrying
    # forever. The process stays alive, so launchd never notices, and the
    # hostname stops resolving - the tunnel looks up in the process table
    # and the address is dead. So the URL is checked, not just the process.
    if [ $((SECONDS % 300)) -lt 4 ]; then
      code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url" 2>/dev/null)"
      # curl prints 000 when it cannot reach the host; treat anything
      # that is not 200 as a dead tunnel.
      if [ "$code" != "200" ]; then
        echo "the Cloudflare tunnel at $url stopped answering (HTTP $code); restarting it"
        # Clear the URL file first. Otherwise the next start reads this
        # same dead hostname from the log, finds it is not answering, and
        # restarts again - a loop that never reaches a working tunnel.
        : > "$URL_FILE"
        kill "$CF_PID" 2>/dev/null
        break
      fi
    fi
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
  wait_for_url 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG_DIR/makgeo-tunnel.log"
}

install_localtunnel() {
  cat > "$RUNNER" <<'RUN_EOF'
#!/bin/bash
# localtunnel forward for MakGeography. The last resort: localtunnel
# shows the visitor a one-time interstitial asking for their public IP
# before the site appears.
set -uo pipefail
PORT="${MAKGEO_PORT:-8781}"
URL_FILE="$HOME/.hermes/logs/makgeo-url.txt"
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

# Fetch cloudflared if it is not already there. It is the fallback, so it
# is only fetched when Serveo is not available.
fetch_cloudflared() {
  [ -x "$CLOUDFLARED" ] && return 0
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
}

if [ -f "$SERVEO_KEY" ]; then
  echo "Using Serveo with the reserved subdomain '$SUBDOMAIN'."
  url="$(install_serveo)"

  # Serveo also serves a warning interstitial to real browsers on an HTTP
  # tunnel, so a second tunnel runs alongside it: a Cloudflare quick
  # tunnel, which serves the site with no interstitial. The Serveo
  # address stays the permanent one; the Cloudflare one is the clean one
  # to hand to a student who needs the site right now.
  fetch_cloudflared
  if [ -x "$CLOUDFLARED" ]; then
    cf_url="$(install_cloudflared)"
    if [ -n "$cf_url" ]; then
      echo "$cf_url" > "$URL_FILE_CF"
      echo "Clean URL (no interstitial): $cf_url"
      echo "Read it later with: cat $URL_FILE_CF"
    fi
  fi

  if [ -z "$url" ]; then
    echo "The Serveo tunnel did not come up. The Cloudflare one may be up."
    url="$cf_url"
  fi
else
  echo "No Serveo key at $SERVEO_KEY, so the address would change on every"
  echo "restart. To get a permanent address, register a key and run this"
  echo "again. Falling back to a Cloudflare quick tunnel for now."
  fetch_cloudflared
  if [ -x "$CLOUDFLARED" ]; then
    url="$(install_cloudflared_as_fallback)"
  else
    command -v npx >/dev/null 2>&1 || {
      echo "Neither cloudflared nor npx is available."
      exit 1
    }
    url="$(install_localtunnel)"
  fi
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

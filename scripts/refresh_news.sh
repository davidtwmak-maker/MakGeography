#!/bin/bash
# Refresh the MakGeography news feed. Fails soft: the previous news.json is
# left untouched if the collector fails.
set -uo pipefail

REPO="${MAKGEO_REPO:-/Users/davidhermes/MakGeography}"
PYTHON="${MAKGEO_PYTHON:-/Users/davidhermes/.hermes/tools/python-3.14.7+20260901-darwin-arm64/bin/python3}"
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

# Check the collector is actually there. A repo directory can exist while
# being the wrong one - an early temp copy, or a half-populated checkout -
# and then the collector fails with a bare "can't open file" that gives no
# clue which directory was wrong.
if [ ! -f "scripts/collect_news.py" ]; then
  log "FAIL: no scripts/collect_news.py under $REPO (wrong repo?)"
  log "      expected the repository at $HOME/MakGeography"
  exit 1
fi

log "starting news refresh"
if "$PYTHON" scripts/collect_news.py >> "$LOG" 2>&1; then
  log "OK: news refreshed"
else
  log "FAIL: collector returned non-zero (previous news.json left in place)"
  exit 1
fi

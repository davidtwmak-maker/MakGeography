#!/bin/bash
# Run the MakGeography FastAPI app in the background.
#
# The password and API key come from ~/.hermes/.env. Neither is written into
# this script or the plist.
set -uo pipefail

REPO="${MAKGEO_REPO:-$HOME/MakGeography}"
PORT="${MAKGEO_PORT:-8781}"
PYTHON="${MAKGEO_PYTHON:-}"
LOGDIR="$HOME/.hermes/logs"

mkdir -p "$LOGDIR"

if [ -z "$PYTHON" ]; then
  PYTHON="$(ls -d "$HOME"/.hermes/tools/python-*/bin/python3 2>/dev/null | head -1)"
fi
[ -z "$PYTHON" ] && PYTHON="$(command -v python3 || true)"

if [ -z "$PYTHON" ]; then
  echo "No python3 found" >&2
  exit 1
fi

# Check the app can actually be imported before starting it. A missing
# dependency (python-multipart is needed for the login form) otherwise shows
# up as a uvicorn traceback and a dead service rather than a clear message.
cd "$REPO" || exit 1

if ! "$PYTHON" -c "import app.main" >/dev/null 2>&1; then
  echo "MakGeography: app.main failed to import; checking dependencies" >&2
  "$PYTHON" - <<'PY' >&2
import importlib, subprocess, sys
need = []
for mod, pkg in (("fastapi", "fastapi"), ("uvicorn", "uvicorn"),
                 ("jinja2", "jinja2"), ("multipart", "python-multipart")):
    try:
        importlib.import_module(mod)
    except ImportError:
        need.append(pkg)
if need:
    print("installing:", " ".join(need), flush=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *need], check=False)
else:
    print("import failed but all known dependencies are present", flush=True)
PY
  if ! "$PYTHON" -c "import app.main" >/dev/null 2>&1; then
    echo "MakGeography: app.main still fails to import; not starting" >&2
    "$PYTHON" -c "import app.main" >&2
    exit 1
  fi
fi

exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"

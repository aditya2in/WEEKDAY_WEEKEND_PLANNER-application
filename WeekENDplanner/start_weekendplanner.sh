#!/usr/bin/env bash
set -euo pipefail

# Start the WeekENDplanner Flask web app (script resides in WeekENDplanner/)
# QUICK CONFIG (edit and save as needed)
# - VENV_DIR: virtual env location
# - APP_MODULE: path to app module
# - HOST/PORT/FLASK_DEBUG: default server bind and debug
# - OPEN_BROWSER: open browser on start (1=yes, 0=no)
# - BROWSER_OPEN_DELAY: seconds to wait before opening browser
#
# Environment variables override these defaults if set.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/venv}"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
FLASK_BIN="$VENV_DIR/bin/flask"
APP_MODULE="${APP_MODULE:-$SCRIPT_DIR/app.py}"
REQ="$SCRIPT_DIR/requirements.txt"
OPEN_BROWSER="${OPEN_BROWSER:-1}"
BROWSER_OPEN_DELAY="${BROWSER_OPEN_DELAY:-1}"

# Create virtual environment if missing
if [ ! -x "$PY" ]; then
  PY_BIN="${PY_BIN:-python3}"
  if ! command -v "$PY_BIN" >/dev/null 2>&1; then
    PY_BIN="python"
  fi
  echo "Creating virtual environment at: $VENV_DIR (using $PY_BIN)"
  "$PY_BIN" -m venv "$VENV_DIR"
fi

# Install/ensure dependencies if a requirements file exists
if [ -f "$REQ" ]; then
  echo "Ensuring Python dependencies from requirements.txt..."
  "$PIP" -q install --upgrade pip >/dev/null 2>&1 || true
  "$PIP" install -r "$REQ" >/dev/null
fi

# Load .env if present (simple KEY=VALUE lines)
if [ -f "$SCRIPT_DIR/.env" ]; then
  # shellcheck disable=SC2046
  export $(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$SCRIPT_DIR/.env" | xargs -d '\n' -I{} echo {}) || true
fi

# Derive host/port/debug from env with sensible defaults
FLASK_RUN_HOST="${HOST:-${FLASK_RUN_HOST:-127.0.0.1}}"
FLASK_RUN_PORT="${PORT:-${FLASK_RUN_PORT:-5002}}"
FLASK_DEBUG="${FLASK_DEBUG:-0}"
export FLASK_RUN_HOST FLASK_RUN_PORT FLASK_DEBUG

# Point Flask CLI at our app module
export FLASK_APP="$APP_MODULE"

echo "Starting WeekENDplanner at http://${FLASK_RUN_HOST}:${FLASK_RUN_PORT} (debug=$FLASK_DEBUG)"
cd "$SCRIPT_DIR"

if [ "$OPEN_BROWSER" = "1" ] || [ "$OPEN_BROWSER" = "true" ] || [ "$OPEN_BROWSER" = "yes" ]; then
  # Open the browser shortly after startup (best-effort, non-blocking)
  browser_host="$FLASK_RUN_HOST"
  if [ "$browser_host" = "0.0.0.0" ] || [ "$browser_host" = "::" ]; then
    browser_host="127.0.0.1"
  fi
  URL="http://${browser_host}:${FLASK_RUN_PORT}"
  if command -v xdg-open >/dev/null 2>&1; then
    (sleep "$BROWSER_OPEN_DELAY"; xdg-open "$URL" >/dev/null 2>&1 || true) &
  elif command -v sensible-browser >/dev/null 2>&1; then
    (sleep "$BROWSER_OPEN_DELAY"; sensible-browser "$URL" >/dev/null 2>&1 || true) &
  elif [ -n "${BROWSER:-}" ]; then
    (sleep "$BROWSER_OPEN_DELAY"; "$BROWSER" "$URL" >/dev/null 2>&1 || true) &
  fi
fi

exec "$FLASK_BIN" run --no-reload

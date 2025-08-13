#!/usr/bin/env bash
set -euo pipefail

# Start the WeekDAYplanner Flask web app (script resides in WeekDAYplanner/)
# - Uses venv inside WeekDAYplanner/venv
# - Ensures dependencies from WeekDAYplanner/requirements.txt
# - Opens the app in your default browser
# - Runs the server in the foreground

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
APP="$SCRIPT_DIR/WeekDAYplannerDAILYnoteCreater.py"
REQ="$SCRIPT_DIR/requirements.txt"
URL="http://127.0.0.1:5000/"

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

# Proactively open browser (non-blocking) if available
if command -v xdg-open >/dev/null 2>&1; then
  (sleep 1; xdg-open "$URL" >/dev/null 2>&1 || true) &
elif command -v sensible-browser >/dev/null 2>&1; then
  (sleep 1; sensible-browser "$URL" >/dev/null 2>&1 || true) &
fi

echo "Starting WeekDAYplanner at $URL"
cd "$SCRIPT_DIR"
exec "$PY" "$APP"

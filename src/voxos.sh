#!/usr/bin/env bash

PIDFILE="/tmp/voxos-prompt.pid"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PROJECT_PYTHON="$PROJECT_ROOT/.venv/bin/python"
LEGACY_PYTHON="$HOME/.local/share/voxos/edge-tts/bin/python"
POPUP="$SCRIPT_DIR/voxos-popup.py"

if [ -x "$PROJECT_PYTHON" ]; then
    PYTHON="$PROJECT_PYTHON"
elif [ -x "$LEGACY_PYTHON" ]; then
    PYTHON="$LEGACY_PYTHON"
else
    echo "Voxos Python environment not found. Create .venv with the project dependencies." >&2
    exit 1
fi

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")

    if kill -0 "$PID" 2>/dev/null; then
        kill -USR1 "$PID"
        exit 0
    fi

    rm -f "$PIDFILE"
fi

"$PYTHON" "$POPUP" &
PID=$!

echo "$PID" > "$PIDFILE"

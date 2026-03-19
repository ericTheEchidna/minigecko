#!/usr/bin/env bash
# Launch MiniGecko, creating the virtualenv if needed.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"

if [ ! -d "$VENV" ]; then
    echo "Creating virtualenv…"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip
    "$VENV/bin/pip" install -e "$DIR"
fi

exec "$VENV/bin/minigecko" "$@"

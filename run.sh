#!/usr/bin/env bash
#
# Run the chesscheat live board reader.
#
# Usage:
#   ./run.sh          # launch the reader (needs a real display + venv)
#
# Requires a real display (X11/Wayland). Run ./setup.sh first to create
# the virtual environment, then activate it or let this script use it
# directly via ./venv/bin/python3.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python3"
fi

exec "$PYTHON" -m chesscheat "$@"

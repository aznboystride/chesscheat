#!/usr/bin/env bash
#
# Regenerate the board fixture images from the committed piece artwork.
#
# Usage:
#   ./generate-fixtures.sh       # rebuild boards/<set>/ PNGs for all piece sets
#
# Requires Pillow. Install dev dependencies first:
#   pip install -r requirements-dev.txt
#
# Only needed when the piece artwork or board layout changes. The generated
# board images are committed to the repository and do not need to be rebuilt
# for normal development or testing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python3"
fi

exec "$PYTHON" "$SCRIPT_DIR/tests/fixtures/generate_boards.py" "$@"

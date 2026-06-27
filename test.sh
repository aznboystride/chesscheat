#!/usr/bin/env bash
#
# Run the test suite.
#
# Usage:
#   ./test.sh                          # full suite (all tests)
#   ./test.sh --fast                   # dependency-free tests only (no numpy/Pillow)
#   ./test.sh --real                   # real-image tests (requires numpy + Pillow)
#   ./test.sh tests.test_board         # single module
#   ./test.sh tests.test_board.FenTests            # single class
#   ./test.sh tests.test_board.FenTests.test_after_e4  # single method
#
# Options and module paths are mutually exclusive.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python3"
fi

case "${1:-}" in
    --fast)
        # Only run the dependency-free tests (board logic + mock pipeline).
        exec "$PYTHON" -m unittest tests.test_board tests.test_recognition -v
        ;;
    --real)
        # Only run tests that require numpy and Pillow (real board images).
        exec "$PYTHON" -m unittest tests.test_real_images tests.test_general_boards -v
        ;;
    "")
        # Full suite: discover every test under tests/.
        exec "$PYTHON" -m unittest discover -s tests -t "$SCRIPT_DIR" -v
        ;;
    *)
        # Pass the argument straight through as a dotted test path.
        exec "$PYTHON" -m unittest "$@"
        ;;
esac

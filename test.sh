#!/usr/bin/env bash
#
# Run the test suite.
#
# Usage:
#   ./test.sh                          # full suite (all tests)
#   ./test.sh --fast                   # dependency-free tests only (no third-party deps)
#   ./test.sh --real                   # dep-requiring tests (numpy/Pillow/python-chess)
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
        # Only run tests that need third-party deps (numpy/Pillow/python-chess).
        exec "$PYTHON" -m unittest tests.test_real_images tests.test_general_boards \
            tests.test_legal_move_filter tests.test_filter_real_images -v
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

#!/usr/bin/env bash
#
# Create a Python virtual environment, install the project dependencies, and
# download a Stockfish engine matching this machine (e.g. the Apple Silicon
# build on an M1-M4 Mac) so the move assist works out of the box.
#
# Usage:
#   ./setup.sh            # creates ./venv, installs deps, installs Stockfish
#
# Environment overrides:
#   PYTHON=...            # interpreter used to build the venv (default python3)
#   STOCKFISH_VERSION=... # pin a release tag, e.g. sf_17.1 (default: latest)
#   SKIP_STOCKFISH=1      # skip the Stockfish download
#
# Afterwards, activate it with:
#   source venv/bin/activate

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="venv"
PYTHON="${PYTHON:-python3}"

echo "Creating virtual environment in ./${VENV_DIR} ..."
"$PYTHON" -m venv "$VENV_DIR"

echo "Upgrading pip ..."
"$VENV_DIR/bin/pip" install --upgrade pip

echo "Installing dependencies from requirements.txt ..."
"$VENV_DIR/bin/pip" install -r requirements.txt

# The GUI windows need Tk. Homebrew Python ships it as a separate, versioned
# formula, so check now and name the matching one rather than letting the
# user discover it at launch. Non-fatal.
if ! "$VENV_DIR/bin/python" -c "import tkinter" >/dev/null 2>&1; then
    PYVER="$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    echo "  Warning: this Python (${PYVER}) has no Tk (tkinter), so the GUI"
    echo "  windows cannot open. On macOS with Homebrew Python, install the"
    echo "  matching Tk (the version must match the venv's Python):"
    echo "      brew install python-tk@${PYVER}"
fi

if [ "${SKIP_STOCKFISH:-0}" = "1" ]; then
    echo "Skipping Stockfish download (SKIP_STOCKFISH=1)."
else
    echo "Installing the Stockfish engine for this machine ..."
    # Install into the venv's bin so it is on PATH when the venv is active and
    # discoverable via shutil.which("stockfish"). Non-fatal: the reader still
    # runs without the move assist if this step fails (e.g. no network).
    if ! "$VENV_DIR/bin/python" "$SCRIPT_DIR/scripts/install_stockfish.py" \
            --dest "$VENV_DIR/bin"; then
        echo "  Warning: Stockfish was not installed; the move assist will be"
        echo "  disabled until a 'stockfish' binary is on PATH (or STOCKFISH_PATH"
        echo "  is set). The board reader itself is unaffected."
    fi
fi

echo
echo "Done. Activate the environment with:"
echo "    source ${VENV_DIR}/bin/activate"
echo "Then run the reader with:"
echo "    python3 -m chesscheat"

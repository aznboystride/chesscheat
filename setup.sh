#!/usr/bin/env bash
#
# Create a Python virtual environment and install the project dependencies.
#
# Usage:
#   ./setup.sh            # creates ./venv and installs requirements.txt
#
# Afterwards, activate it with:
#   source venv/bin/activate

set -euo pipefail

VENV_DIR="venv"
PYTHON="${PYTHON:-python3}"

echo "Creating virtual environment in ./${VENV_DIR} ..."
"$PYTHON" -m venv "$VENV_DIR"

echo "Upgrading pip ..."
"$VENV_DIR/bin/pip" install --upgrade pip

echo "Installing dependencies from requirements.txt ..."
"$VENV_DIR/bin/pip" install -r requirements.txt

echo
echo "Done. Activate the environment with:"
echo "    source ${VENV_DIR}/bin/activate"
echo "Then run the reader with:"
echo "    python3 chessboard_state.py"

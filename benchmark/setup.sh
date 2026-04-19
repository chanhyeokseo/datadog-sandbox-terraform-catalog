#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "Creating venv at $VENV_DIR ..."
python3 -m venv "$VENV_DIR"

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "Setup complete. Usage:"
echo ""
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "  # Run full benchmark (5 runs each for IDLE + EC2 deploy)"
echo "  python -m benchmark run"
echo ""
echo "  # Re-generate report from latest results"
echo "  python -m benchmark report"
echo ""

#!/usr/bin/env bash
# ==============================================================================
# Google Photos Local Takeout Gallery - Linux/macOS Startup Script
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Prevent multi-threading library contention
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Locate Python executable
PYTHON_BIN=""
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "[!] ERROR: Python 3.10+ is required but was not found."
    echo "    Please install Python 3.10+ and activate your environment."
    exit 1
fi

echo "=============================================================================="
echo "  GOOGLE PHOTOS LOCAL TAKEOUT ARCHIVE LAUNCHER"
echo "=============================================================================="
echo "[+] Using Python: $PYTHON_BIN"
echo "[+] Launching application..."
echo "=============================================================================="

exec "$PYTHON_BIN" run.py "$@"

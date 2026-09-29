#!/usr/bin/env bash
# Runner for compiling and inspecting sigmaLang source programs

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${REPO_DIR}/.venv/bin/python3"
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi

if [ $# -eq 0 ]; then
    echo "Usage: ./run.sh <source_file> [--ast]"
    exit 1
fi

"$PYTHON" "${REPO_DIR}/compiler.py" --ast "$@"

#!/usr/bin/env bash
# Runner for compiling and running sigmaLang source programs
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${REPO_DIR}/.venv/bin/python3"
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi

if [ -d "/home/ubuntu/lcd/lib/python3.12/site-packages" ]; then
    export PYTHONPATH="/home/ubuntu/lcd/lib/python3.12/site-packages${PYTHONPATH:+:$PYTHONPATH}"
elif [ -d "$HOME/lcd/lib/python3.12/site-packages" ]; then
    export PYTHONPATH="$HOME/lcd/lib/python3.12/site-packages${PYTHONPATH:+:$PYTHONPATH}"
fi

if [ $# -eq 0 ]; then
    echo "Usage: ./run.sh <source_file> [output.ll] [--ast]"
    exit 1
fi

if [ "$1" = "--ast" ]; then
    exec "$PYTHON" "${REPO_DIR}/compiler.py" --ast "$2"
elif [ "$2" = "--ast" ]; then
    exec "$PYTHON" "${REPO_DIR}/compiler.py" --ast "$1"
fi

INPUT="$1"
OUTPUT="${2:-/tmp/sigmalang_out.ll}"

# Compile to LLVM IR
"$PYTHON" "${REPO_DIR}/compiler.py" "$INPUT" "$OUTPUT"

IN_FILE="${INPUT%.*}.in"
INPUT_REDIR=""
if [ -f "$IN_FILE" ] && [ -t 0 ]; then
    exec < "$IN_FILE"
fi

# Run using lli/clang or MCJIT JIT runner
if command -v lli &> /dev/null; then
    lli "$OUTPUT"
elif command -v llc &> /dev/null && command -v clang &> /dev/null; then
    OBJ="/tmp/sigmalang_out.o"
    BIN="/tmp/sigmalang_bin"
    llc -filetype=obj -relocation-model=pic "$OUTPUT" -o "$OBJ"
    clang -fPIE "$OBJ" -o "$BIN"
    "$BIN"
else
    "$PYTHON" -c "
import sys
from pathlib import Path
for _p in ('/home/ubuntu/lcd/lib/python3.12/site-packages', str(Path.home() / 'lcd/lib/python3.12/site-packages')):
    if _p not in sys.path and Path(_p).exists():
        sys.path.insert(0, _p)
import llvmlite.binding as llvm
import ctypes

llvm.initialize_native_target()
llvm.initialize_native_asmprinter()

with open(r'$OUTPUT', 'r', encoding='utf-8') as f:
    ll_text = f.read()

llvm_mod = llvm.parse_assembly(ll_text)
target_machine = llvm.Target.from_default_triple().create_target_machine()
engine = llvm.create_mcjit_compiler(llvm_mod, target_machine)
engine.finalize_object()
func_ptr = engine.get_function_address('main')
cfunc = ctypes.CFUNCTYPE(ctypes.c_int32)(func_ptr)
res = cfunc()
"
fi

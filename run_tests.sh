#!/usr/bin/env bash

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${REPO_DIR}/.venv/bin/python3"
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi

echo "=== Running sigmaLang Test Suite ==="
OK_COUNT=0
FAIL_COUNT=0
TOTAL=0

# Test Happy Path (tests/ok)
if [ -d "${REPO_DIR}/tests/ok" ]; then
    for src in "${REPO_DIR}/tests/ok"/*.src; do
        [ -e "$src" ] || continue
        TOTAL=$((TOTAL + 1))
        test_name="$(basename "$src" .src)"
        expected_ast="${REPO_DIR}/tests/ok/${test_name}.ast"

        actual_output="$("$PYTHON" "${REPO_DIR}/compiler.py" --ast "$src" 2>&1)"
        exit_code=$?

        if [ $exit_code -ne 0 ]; then
            echo "❌ [FAIL] tests/ok/${test_name}: exited with non-zero code ${exit_code}"
            echo "$actual_output"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            continue
        fi

        if [ -f "$expected_ast" ]; then
            expected_content="$(cat "$expected_ast")"
            if [ "$actual_output" == "$expected_content" ]; then
                echo "✅ [PASS] tests/ok/${test_name}"
                OK_COUNT=$((OK_COUNT + 1))
            else
                echo "❌ [FAIL] tests/ok/${test_name}: output mismatch"
                echo "--- Expected ---"
                echo "$expected_content"
                echo "--- Actual ---"
                echo "$actual_output"
                FAIL_COUNT=$((FAIL_COUNT + 1))
            fi
        else
            echo "⚠️  [SKIP] tests/ok/${test_name}: missing .ast file"
        fi
    done
fi

# Test Error Scenarios (tests/err)
if [ -d "${REPO_DIR}/tests/err" ]; then
    for src in "${REPO_DIR}/tests/err"/*.src; do
        [ -e "$src" ] || continue
        TOTAL=$((TOTAL + 1))
        test_name="$(basename "$src" .src)"
        expected_err="${REPO_DIR}/tests/err/${test_name}.err"

        # Capture stderr
        actual_output="$("$PYTHON" "${REPO_DIR}/compiler.py" --ast "$src" 2>&1 1>/dev/null)"
        exit_code=$?

        if [ $exit_code -eq 0 ]; then
            echo "❌ [FAIL] tests/err/${test_name}: expected error, but exited with code 0"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            continue
        fi

        if [ -f "$expected_err" ]; then
            expected_content="$(cat "$expected_err")"
            trimmed_actual="$(echo "$actual_output" | head -n 1 | tr -d '\r')"
            trimmed_expected="$(echo "$expected_content" | head -n 1 | tr -d '\r')"
            if [ "$trimmed_actual" == "$trimmed_expected" ]; then
                echo "✅ [PASS] tests/err/${test_name}"
                OK_COUNT=$((OK_COUNT + 1))
            else
                echo "❌ [FAIL] tests/err/${test_name}: error message mismatch"
                echo "--- Expected ---"
                echo "$trimmed_expected"
                echo "--- Actual ---"
                echo "$trimmed_actual"
                FAIL_COUNT=$((FAIL_COUNT + 1))
            fi
        else
            echo "⚠️  [SKIP] tests/err/${test_name}: missing .err file"
        fi
    done
fi

echo ""
echo "=== Test Results: Total: ${TOTAL} | Passed: ${OK_COUNT} | Failed: ${FAIL_COUNT} ==="

if [ $FAIL_COUNT -eq 0 ] && [ $TOTAL -gt 0 ]; then
    exit 0
else
    exit 1
fi

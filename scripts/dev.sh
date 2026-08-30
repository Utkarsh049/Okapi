#!/usr/bin/env bash
set -e

# Find OPA binary
if command -v opa &> /dev/null; then
    OPA_BIN="opa"
elif [ -f "./.tools/opa" ]; then
    OPA_BIN="./.tools/opa"
elif [ -f "./.tools/opa.exe" ]; then
    OPA_BIN="./.tools/opa.exe"
else
    echo "OPA binary not found. Placing standalone OPA into .tools/opa..."
    mkdir -p .tools
    curl -L -o .tools/opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64_static
    chmod +x .tools/opa
    OPA_BIN="./.tools/opa"
fi

echo "=================================================="
echo " Starting Okapi Local Dev Stack (OPA + FastAPI)  "
echo "=================================================="

# Clean up background OPA process on exit/Ctrl+C
OPA_PID=""
cleanup() {
    echo ""
    echo "Shutting down servers..."
    if [ -n "$OPA_PID" ]; then
        kill "$OPA_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Start OPA in background if not already running on port 8181
if ! curl -s http://localhost:8181/health >/dev/null 2>&1; then
    echo "-> Starting OPA policy server on http://localhost:8181..."
    "$OPA_BIN" run --server --addr localhost:8181 packages/policies > /dev/null 2>&1 &
    OPA_PID=$!
    sleep 0.5
else
    echo "-> OPA server is already running on port 8181."
fi

echo "-> Starting FastAPI API server on http://localhost:8000..."
echo "-> Swagger Docs: http://localhost:8000/docs"
echo "=================================================="

# Run FastAPI in foreground
uv run --package okapi-api uvicorn okapi_api.main:app --reload --port 8000

#!/usr/bin/env bash
# One-time local setup.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync
[ -f .env ] || cp .env.example .env
echo "Done. Next: 'make run' (API only) or 'make compose-up' (API + OPA + Postgres)."

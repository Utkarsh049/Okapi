#!/usr/bin/env bash
# Thin wrapper around Alembic for the okapi-api member. Args pass straight through:
#   scripts/migrate.sh upgrade head
#   scripts/migrate.sh revision --autogenerate -m "add fields table"
set -euo pipefail
cd "$(dirname "$0")/.."

uv run --package okapi-api alembic -c apps/api/alembic.ini "$@"

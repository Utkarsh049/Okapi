#!/usr/bin/env bash
# Format + autofix the whole workspace. ruff sorts imports and applies lint fixes;
# black is the sole code formatter (architecture doc section 12).
set -euo pipefail
cd "$(dirname "$0")/.."

uv run ruff check --fix .
uv run black .

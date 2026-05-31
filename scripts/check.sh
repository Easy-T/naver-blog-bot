#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Each step is its own statement. Under `set -e`, a failure in a
# `cmd1 && cmd2 && cmd3` chain does NOT abort the script when a *non-final*
# command fails (bash exempts && lists except the final command), so a
# ruff-format failure used to silently skip pytest and exit 0. Separate
# statements make every failure fatal.
echo "==> ruff check"
uv run ruff check .

echo "==> ruff format --check"
uv run ruff format --check .

echo "==> pytest"
uv run pytest -q

echo "== check complete =="

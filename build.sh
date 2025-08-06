#!/usr/bin/env bash
set -euo pipefail

CURRENT_TIME=$(date +%Y-%m-%dT%H:%M:%S)
# deps
uv sync

# formatting, docstrings, linting, and type checking
uv run pre-commit run --show-diff-on-failure --color=always --all-files

# tests and coverage
export PREFECT_SERVER_DATABASE_CONNECTION_URL="sqlite+aiosqlite:///./integration-tests.db"
# Could just run tests without coverage with `uv run pytest tests`
uv run coverage run -m pytest tests -vv
uv run coverage report
# view html report in browser with live server vscode extension
uv run coverage html
uv run mkdocs build --verbose --clean

# build package
uv build

ELAPSED_TIME=$(($(date +%s) - $(date -d "$CURRENT_TIME" +%s)))

echo "All tasks passed successfully in $ELAPSED_TIME seconds!"
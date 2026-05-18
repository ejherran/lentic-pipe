#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"

if [[ ! -d .git ]]; then
  echo "Run this from the repository root."
  exit 2
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python || true)"
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "Python is not available. Install the project environment first:"
  echo "  poetry install --with dev,modeling,sources,data-versioning"
  exit 2
fi

"$PYTHON_BIN" src/data/prepare_commit_artifacts.py "$@"

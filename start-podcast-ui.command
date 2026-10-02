#!/bin/sh
set -eu
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "First-time setup. This may take a minute."
  python3 -m venv .venv
  .venv/bin/python -m pip install -e .
fi

exec .venv/bin/python -m podcast_pipeline ui

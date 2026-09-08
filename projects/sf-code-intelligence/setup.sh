#!/usr/bin/env bash
set -euo pipefail

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]" --quiet

if [ ! -d "fixtures" ]; then
    echo "Missing fixtures/ directory. Ensure fixture files are checked into the repository."
    exit 1
fi

echo "Setup complete. Run: source .venv/bin/activate"

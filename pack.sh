#!/usr/bin/env bash
# pack.sh — bundle the OptionCalculator web server for deployment
#
# Creates OptionCalculator.tgz one level above this repo containing:
#
#   OptionCalculator/          web server source only (no desktop files or tests)
#     requirements.txt
#     src/main_web.py
#     src/option_service.py
#     src/yahoo_data.py
#     src/option_pricing.py
#     src/config_manager.py
#     src/app_icon.png
#     src/ui_web/
#   option_lib/                shared pricing + data library (sibling directory)
#
# Deploy on the server
# --------------------
#   tar -xzf OptionCalculator.tgz
#   cd OptionCalculator
#   python -m pip install -r requirements.txt
#   python -m pip install ../option_lib
#   export OPTION_PWD=yourpassword
#   PYTHONPATH=src python src/main_web.py          # Flask dev server (port 5001)
#
#   # Production (gunicorn):
#   PYTHONPATH=src OPTION_PWD=yourpassword \
#     gunicorn --bind 0.0.0.0:5001 --chdir src main_web:app
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(basename "$SCRIPT_DIR")"
PARENT="$(dirname "$SCRIPT_DIR")"
OUT="$PARENT/$PROJECT.tgz"

# Verify the shared library is present
if [[ ! -d "$PARENT/option_lib" ]]; then
    echo "ERROR: option_lib not found at $PARENT/option_lib" >&2
    exit 1
fi

rm -f "$OUT"

# Desktop-only files (calculator_*.py, main.py, utils/, test_*.py) and dev
# artifacts are intentionally omitted to keep the bundle lean.
tar -czf "$OUT" \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.egg-info' \
    -C "$PARENT" \
    "$PROJECT/requirements.txt" \
    "$PROJECT/src/main_web.py" \
    "$PROJECT/src/option_service.py" \
    "$PROJECT/src/yahoo_data.py" \
    "$PROJECT/src/option_pricing.py" \
    "$PROJECT/src/config_manager.py" \
    "$PROJECT/src/app_icon.png" \
    "$PROJECT/src/ui_web" \
    option_lib

SIZE=$(du -sh "$OUT" | cut -f1)
echo "Created: $OUT  ($SIZE)"
echo ""
echo "Deploy:"
echo "  tar -xzf $PROJECT.tgz && cd $PROJECT"
echo "  python -m pip install -r requirements.txt"
echo "  python -m pip install ../option_lib"
echo "  export OPTION_PWD=yourpassword"
echo "  PYTHONPATH=src python src/main_web.py"

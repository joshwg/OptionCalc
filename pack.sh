#!/usr/bin/env bash
# pack.sh — bundle the OptionCalculator web server for deployment
#
# Creates ../OptionCalculator.tgz containing:
#
#   OptionCalculator/          web server source only (no desktop files or tests)
#     requirements.txt
#     src/  (excluding calculator_*.py main.py utils/ tests/)
#   option_lib/                shared pricing + data library (sibling directory)
#
# Deploy on the server:
#   tar -xzf OptionCalculator.tgz
#   cd OptionCalculator/src
#   pip install -r ../requirements.txt
#   pip install ../../option_lib
#   export OPTION_PWD=yourpassword
#   python main_web.py                              # Flask dev server (port 5001)
#
#   # Production (gunicorn):
#   OPTION_PWD=yourpassword \
#     gunicorn --bind 0.0.0.0:5001 main_web:app
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(basename "$SCRIPT_DIR")"
PARENT="$(dirname "$SCRIPT_DIR")"
OUT="$PARENT/$PROJECT.tgz"

if [[ ! -d "$PARENT/option_lib" ]]; then
    echo "ERROR: option_lib not found at $PARENT/option_lib" >&2
    exit 1
fi

rm -f "$OUT"

tar -czf "$OUT" \
    --exclude='.git' \
    --exclude='.gitignore' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.egg-info' \
    --exclude='*.bat' \
    --exclude='.pytest_cache' \
    --exclude='*/.pytest_cache' \
    --exclude='OptionCalculator/src/calculator_*.py' \
    --exclude='OptionCalculator/src/main.py' \
    --exclude='OptionCalculator/src/utils' \
    --exclude='OptionCalculator/src/tests' \
    -C "$PARENT" \
    "$PROJECT" \
    option_lib

SIZE=$(du -sh "$OUT" | cut -f1)
echo "Created: $OUT  ($SIZE)"
echo ""
echo "Deploy:"
echo "  tar -xzf $PROJECT.tgz && cd $PROJECT/src"
echo "  pip install -r ../requirements.txt && pip install ../../option_lib"
echo "  export OPTION_PWD=yourpassword"
echo "  python main_web.py"

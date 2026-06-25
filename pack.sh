#!/usr/bin/env bash
# pack.sh — bundle the OptionCalculator web server for deployment
#
# Creates ../OptionCalculator.tgz containing:
#
#   OptionCalculator/          web server source (no desktop files or tests)
#     requirements.txt
#     src/
#       main_web.py, option_pricing.py, option_service.py, ...
#       ui_web/   (templates + static assets)
#   option_lib/                shared library (sibling directory)
#
# Desktop-only files excluded: main.py, calculator_window.py,
#   calculator_operations.py, config_manager.py, utils/
#
# Deploy on the server:
#   tar -xzf OptionCalculator.tgz && cd OptionCalculator/src
#   pip install -r ../requirements.txt && pip install ../../option_lib
#   export OPTION_PWD=yourpassword
#
#   # Dev server:
#   python main_web.py
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

OPT_LIB="$PARENT/option_lib"
if [[ ! -d "$OPT_LIB" ]]; then
    echo "ERROR: option_lib not found at $OPT_LIB" >&2
    exit 1
fi

rm -f "$OUT"

tar -czf "$OUT" \
    --mode='u=rwX,g=rwX,o=rX' \
    --exclude='.git' \
    --exclude='.gitignore' \
    --exclude='.claude' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.bat' \
    --exclude='*.sh' \
    --exclude='*.md' \
    --exclude='*/tests' \
    --exclude='*/build' \
    --exclude='.pytest_cache' \
    --exclude='*/.pytest_cache' \
    --exclude="./$PROJECT/src/main.py" \
    --exclude="./$PROJECT/src/calculator_window.py" \
    --exclude="./$PROJECT/src/calculator_operations.py" \
    --exclude="./$PROJECT/src/config_manager.py" \
    --exclude="./$PROJECT/src/utils" \
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

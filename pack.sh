#!/usr/bin/env bash
# pack.sh — bundle the OptionCalculator web server for deployment
#
# Creates ../OptionCalculator.tgz containing:
#
#   OptionCalculator/
#     requirements.txt
#     src/
#       main_web.py
#       option_pricing.py
#       option_service.py
#       config.py
#       config_manager.py
#       yahoo_data.py
#       ui_web/            (templates + static assets)
#   option_lib/
#     pyproject.toml
#     option_lib/          (the installable package)
#
# Deploy on the server:
#   tar -xzf OptionCalculator.tgz
#   pip install ./option_lib
#   pip install -r OptionCalculator/requirements.txt
#   export OPTION_PWD=yourpassword
#   cd OptionCalculator/src
#   gunicorn --bind 0.0.0.0:5001 main_web:app
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(basename "$SCRIPT_DIR")"
PARENT="$(dirname "$SCRIPT_DIR")"
OUT="$PARENT/$PROJECT.tgz"
SRC="$SCRIPT_DIR/src"
OPT_LIB="$PARENT/option_lib"

if [[ ! -d "$OPT_LIB" ]]; then
    echo "ERROR: option_lib not found at $OPT_LIB" >&2
    exit 1
fi

rm -f "$OUT"

# ── Web server source files ────────────────────────────────────────────────
WEB_SRC_FILES=(
    main_web.py
    option_pricing.py
    option_service.py
    config.py
    config_manager.py
    yahoo_data.py
)

# Build the tar from an explicit file list so nothing unintended sneaks in.
{
    # OptionCalculator/requirements.txt
    echo "$PROJECT/requirements.txt"

    # OptionCalculator/src/<file>
    for f in "${WEB_SRC_FILES[@]}"; do
        echo "$PROJECT/src/$f"
    done

    # OptionCalculator/src/ui_web/ (all templates + static assets)
    find "$SRC/ui_web" -type f \
        ! -name '*.pyc' \
        ! -name '*.pyo' \
        ! -path '*/__pycache__/*' \
        | sed "s|$PARENT/||"

    # option_lib/pyproject.toml + the package directory
    echo "option_lib/pyproject.toml"
    find "$OPT_LIB/option_lib" -type f \
        ! -name '*.pyc' \
        ! -name '*.pyo' \
        ! -path '*/__pycache__/*' \
        | sed "s|$PARENT/||"

} | tar -czf "$OUT" -C "$PARENT" --files-from=-

SIZE=$(du -sh "$OUT" | cut -f1)
echo "Created: $OUT  ($SIZE)"
echo ""
echo "Deploy:"
echo "  tar -xzf $PROJECT.tgz"
echo "  pip install ./option_lib"
echo "  pip install -r $PROJECT/requirements.txt"
echo "  export OPTION_PWD=yourpassword"
echo "  cd $PROJECT/src && python main_web.py"

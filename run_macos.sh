#!/usr/bin/env zsh
set -e

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Setting up Python virtual environment in $SCRIPT_DIR/.venv ..."
    python3 -m venv "$SCRIPT_DIR/.venv"
    "$SCRIPT_DIR/.venv/bin/pip" install --upgrade pip
    "$SCRIPT_DIR/.venv/bin/pip" install -e "$SCRIPT_DIR/ok-script[default,ocr,qt,web]" \
        pyobjc-framework-Quartz pyobjc-framework-Cocoa pyobjc-framework-ApplicationServices \
        onnxruntime opencv-python polib
fi

export PYTHONPATH="$SCRIPT_DIR/ok-script:$SCRIPT_DIR:${PYTHONPATH:-}"

case "${1:-}" in
    --web)
        shift
        exec "$PYTHON_BIN" main_web.py "$@"
        ;;
    --debug)
        shift
        exec "$PYTHON_BIN" main_debug.py "$@"
        ;;
    *)
        exec "$PYTHON_BIN" main.py "$@"
        ;;
esac

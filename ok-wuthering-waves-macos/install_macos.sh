#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo 'Install native Apple silicon Python 3.12 first (python.org or Homebrew), then rerun this script.' >&2
    exit 1
fi
"$PYTHON_BIN" - <<'PY'
import platform, sys
if platform.system() != 'Darwin' or platform.machine() != 'arm64':
    sys.exit('Use native arm64 Python on an Apple silicon Mac, without Rosetta.')
if sys.version_info[:2] != (3, 12):
    sys.exit('This preview is pinned for Python 3.12.')
if int(platform.mac_ver()[0].split('.')[0]) < 14:
    sys.exit('ScreenCaptureKit screenshots require macOS 14 or newer.')
PY
if [ ! -x .venv/bin/python ]; then
    "$PYTHON_BIN" -m venv .venv
fi
.venv/bin/python - <<'PY'
import platform, sys
if platform.machine() != 'arm64' or sys.version_info[:2] != (3, 12):
    sys.exit('Existing .venv is not arm64 Python 3.12. Rename it and rerun setup.')
PY
.venv/bin/python -m pip install --only-binary=:all: -r requirements-macos.txt
.venv/bin/python -m macos_port.download_assets
echo 'Setup complete. Next: .venv/bin/python main_macos.py doctor --request-permissions'

#!/usr/bin/env bash
# Packages zk_sidecar.py as a standalone binary -- so an installed bridge
# (Windows PC or Raspberry Pi) doesn't need Python/pyzk present, only the
# one file this produces. Run on each target platform/arch; PyInstaller
# doesn't cross-compile.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .build-venv
. .build-venv/bin/activate 2>/dev/null || . .build-venv/Scripts/activate
pip install -r requirements.txt

pyinstaller --onefile --name zk_sidecar zk_sidecar.py
echo "Built: dist/zk_sidecar (or dist/zk_sidecar.exe on Windows)"

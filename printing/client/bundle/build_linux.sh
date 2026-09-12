#!/bin/bash
set -euo pipefail
stage="$PWD/stage/printer-client-linux"
mkdir -p "$stage"
runtime='cpython-3.12.14+20260901-x86_64-unknown-linux-gnu-install_only.tar.gz'
curl --fail --location --retry 3 "https://github.com/astral-sh/python-build-standalone/releases/download/20260901/$runtime" -o python-linux.tar.gz
printf '%s\n' '936c246dfdbbfa7cb22dd01814a21f582a892689fae96b06071a5e433baffa22  python-linux.tar.gz' | sha256sum --check
tar -xzf python-linux.tar.gz -C "$stage"
"$stage/python/bin/python3" -m pip install --only-binary=:all: -r printing/client/bundle/requirements.txt
"$stage/python/bin/python3" -m pip check
cp printing/client/printer.py printing/client/test_room_lookup.py printing/client/.env.sample printing/client/README.md "$stage/"
cp printing/client/bundle/run.sh "$stage/run.sh"
cp printing/client/bundle/check_linux_runtime.py "$stage/check_runtime.py"
cp LICENSE "$stage/LICENSE.txt"
chmod +x "$stage/run.sh"
printf 'Linux x86_64 printer client\nSource commit: %s\nPython: %s\nUses the host CUPS printer queue (lp/lpstat/cancel).\n' "$(git rev-parse HEAD)" "$runtime" > "$stage/BUNDLE-NOTES.txt"
tar -czf printer-client-linux-x86_64.tar.gz -C stage printer-client-linux

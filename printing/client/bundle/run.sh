#!/bin/sh
set -eu
cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# Ignore an activated venv and user Python packages on the teacher's laptop.
unset PYTHONHOME PYTHONPATH
export PYTHONNOUSERSITE=1
if [ ! -x python/bin/python3 ]; then
    printf '%s\n' 'Bundled Python missing. Extract the complete Linux archive again.' >&2
    exit 1
fi
for command in lp lpstat cancel; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf '%s\n' "Ubuntu printing command '$command' is missing. Install cups-client and configure the printer in Settings." >&2
        exit 1
    fi
done
if [ "${1:-}" = --check ]; then
    exec ./python/bin/python3 -I check_runtime.py .
fi
if [ ! -f .env ]; then
    printf '%s\n' 'Copy your configured .env beside run.sh (room 2: PHYSICAL_PRINTER_ID=2).' >&2
    exit 1
fi
exec ./python/bin/python3 -s printer.py

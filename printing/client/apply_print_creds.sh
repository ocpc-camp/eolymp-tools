#!/bin/bash
# (Re)create the daemon's SMB print queue from the login+password in
# print_creds.env — the one place to update the printer credentials.
#
#   cp print_creds.env.sample print_creds.env   # first time
#   $EDITOR print_creds.env                      # set PRINT_SMB_USER / _PASSWORD
#   ./apply_print_creds.sh                        # apply (repeat to update)
#
# No sudo is needed where the local CUPS admin policy allows it (macOS admins).
# The password is embedded in the queue's device URI (root-readable
# printers.conf); the plaintext print_creds.env is gitignored.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CREDS="${OCPC_PRINT_CREDS:-$DIR/print_creds.env}"
if [ ! -f "$CREDS" ]; then
    echo "ERROR: no creds file at $CREDS" >&2
    echo "  cp '$DIR/print_creds.env.sample' '$CREDS'  then edit it" >&2
    exit 1
fi
set -a; . "$CREDS"; set +a

: "${PRINT_QUEUE:=ccstung1_auto}"
: "${PRINT_SMB_SERVER:=ccstung1.ad.cityu.edu.hk}"
: "${PRINT_SMB_SHARE:=csc_quota_queue}"
: "${PRINT_PPD_FROM:=csc_quota_queue}"
: "${PRINT_MEDIA:=A4}"

if [ -z "${PRINT_SMB_USER:-}" ] || [ -z "${PRINT_SMB_PASSWORD:-}" ]; then
    echo "ERROR: set PRINT_SMB_USER and PRINT_SMB_PASSWORD in $CREDS" >&2
    exit 1
fi

PPD="/private/etc/cups/ppd/${PRINT_PPD_FROM}.ppd"
[ -r "$PPD" ] || PPD="/etc/cups/ppd/${PRINT_PPD_FROM}.ppd"
if [ ! -r "$PPD" ]; then
    echo "ERROR: reference PPD not readable: $PPD" >&2
    echo "  set PRINT_PPD_FROM to an existing, working queue (see 'lpstat -p')." >&2
    exit 1
fi

ENC="$(PW="$PRINT_SMB_PASSWORD" python3 -c 'import os,urllib.parse;print(urllib.parse.quote(os.environ["PW"], safe=""))')"
URI="smb://${PRINT_SMB_USER}:${ENC}@${PRINT_SMB_SERVER}/${PRINT_SMB_SHARE}"

lpadmin -p "$PRINT_QUEUE" -v "$URI" -P "$PPD" -E
lpadmin -p "$PRINT_QUEUE" -o printer-is-shared=false -o media="$PRINT_MEDIA" 2>/dev/null || true
cupsenable "$PRINT_QUEUE" 2>/dev/null || true
cupsaccept "$PRINT_QUEUE" 2>/dev/null || true

echo "OK: queue '$PRINT_QUEUE' now uses smb://${PRINT_SMB_USER}:***@${PRINT_SMB_SERVER}/${PRINT_SMB_SHARE} (media=$PRINT_MEDIA)"
echo "Make sure PHYSICAL_PRINTER_NAME=$PRINT_QUEUE in .env, then restart: ./run_services.sh"

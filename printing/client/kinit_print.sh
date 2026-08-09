#!/bin/bash
# Obtain a Kerberos ticket for the CityU print account so the printer daemon can
# use the ORIGINAL negotiate queue (e.g. ccstung1_ad_cityu_edu_hk) WITHOUT any
# password stored in CUPS. It reuses the password already saved in your login
# keychain for the SMB print server, so nothing new is stored here and it stays
# in sync if that password is updated.
#
# Run in Terminal.app (a GUI login session) — the keychain prompt can't appear
# over SSH. Choose "Always Allow" on the prompt to make later refreshes silent.
# The ticket lasts ~10 hours; re-run to refresh (or schedule it via launchd/cron
# once "Always Allow" is set).
#
#   ./kinit_print.sh                     # principal shanzheng9@AD.CITYU.EDU.HK
#   ./kinit_print.sh user@REALM          # override principal
#   OCPC_SMB_SERVER=host ./kinit_print.sh   # override the keychain server
set -euo pipefail

PRINCIPAL="${1:-${OCPC_KRB_PRINCIPAL:-shanzheng9@AD.CITYU.EDU.HK}}"
SERVER="${OCPC_SMB_SERVER:-ccstung1.ad.cityu.edu.hk}"

if ! PW="$(security find-internet-password -s "$SERVER" -w 2>/dev/null)"; then
    echo "ERROR: couldn't read the keychain password for '$SERVER'." >&2
    echo "Run this in Terminal.app and approve the keychain prompt (once you" >&2
    echo "print manually to that server, macOS saves the password there)." >&2
    exit 1
fi

# Heimdal (macOS) kinit reads the password from stdin with --password-file=STDIN.
printf '%s' "$PW" | kinit --password-file=STDIN "$PRINCIPAL"
unset PW

echo "== ticket =="
klist
echo "OK: point PHYSICAL_PRINTER_NAME at the negotiate queue and it will"
echo "authenticate with this ticket (no password stored in CUPS)."

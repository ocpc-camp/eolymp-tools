#!/bin/bash
# Start / restart / stop the OCPC laptop services:
#   - discord/pinger.py           Eolymp tickets -> Discord
#   - printing/client/printer.py  Eolymp print queue -> physical printer
#
# On macOS it also keeps the machine awake (caffeinate) for as long as the
# daemons run, then releases automatically. Idempotent: run again to restart.
# Logs: ~/ocpc_pinger.log, ~/ocpc_printer.log   PIDs: ~/ocpc_*.pid
#
#   ./run_services.sh            # start or restart both
#   ./run_services.sh stop
#   ./run_services.sh status
#
# NOTE: on a laptop, keep it PLUGGED IN with the lid OPEN — caffeinate cannot
# stop clamshell (lid-closed) sleep, and on battery system-sleep still applies.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${OCPC_PYTHON:-$ROOT/discord/.venv/bin/python}"
CAFFEINATE_FLAGS="${OCPC_CAFFEINATE_FLAGS:--i -m -s}"  # idle, disk, system sleep
# Which services to manage. A SECOND print laptop should run the printer only
# (a second pinger would double-post to Discord):  OCPC_SERVICES=printer ...
SERVICES="${OCPC_SERVICES:-pinger printer}"
_want() { case " $SERVICES " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

PINGER_DIR="$ROOT/discord";           PINGER_SCRIPT="pinger.py"
PRINTER_DIR="$ROOT/printing/client";  PRINTER_SCRIPT="printer.py"
PINGER_LOG="$HOME/ocpc_pinger.log";   PINGER_PID="$HOME/ocpc_pinger.pid"
PRINTER_LOG="$HOME/ocpc_printer.log"; PRINTER_PID="$HOME/ocpc_printer.pid"

_alive() { [ -f "$1" ] && kill -0 "$(cat "$1" 2>/dev/null)" 2>/dev/null; }

_start() {  # label dir script log pidfile
    local label="$1" dir="$2" script="$3" log="$4" pf="$5"
    # exec inside the subshell so $! is the daemon's REAL pid; </dev/null and
    # redirected output so it fully detaches (won't hold an ssh session open).
    ( cd "$dir" && exec env PYTHONUNBUFFERED=1 nohup "$PY" "$script" >"$log" 2>&1 </dev/null ) &
    local pid=$!
    echo "$pid" >"$pf"
    if command -v caffeinate >/dev/null 2>&1; then
        ( exec nohup caffeinate $CAFFEINATE_FLAGS -w "$pid" >/dev/null 2>&1 </dev/null ) &
    fi
    echo "  $label: started (pid $pid) -> $log"
}

_stop_svc() {  # pidfile pattern
    _alive "$1" && kill "$(cat "$1")" 2>/dev/null
    rm -f "$1"
    pkill -f "$2" 2>/dev/null  # stragglers; daemon argv is the bare script name
}
_stop() {
    _want pinger  && _stop_svc "$PINGER_PID"  'pinger.py'
    _want printer && _stop_svc "$PRINTER_PID" 'printer.py'
}

case "${1:-restart}" in
    stop)
        echo "stopping OCPC services..."; _stop; echo "stopped."
        ;;
    status)
        _alive "$PINGER_PID"  && echo "  pinger:  RUNNING (pid $(cat "$PINGER_PID"))"  || echo "  pinger:  stopped"
        _alive "$PRINTER_PID" && echo "  printer: RUNNING (pid $(cat "$PRINTER_PID"))" || echo "  printer: stopped"
        command -v pmset >/dev/null 2>&1 && { pmset -g | grep -iE '^ *sleep\b'; pmset -g batt | tail -1; }
        ;;
    *)  # start | restart
        [ -x "$PY" ] || { echo "ERROR: python not found at $PY (set OCPC_PYTHON)"; exit 1; }
        # Optional: get a Kerberos ticket first, so the daemon can use the
        # ORIGINAL negotiate queue (no password stored in CUPS) instead of the
        # embedded-credential *_auto queue. Run from Terminal.app so the keychain
        # prompt can appear:  OCPC_KINIT=1 ./run_services.sh
        if [ -n "${OCPC_KINIT:-}" ]; then
            echo "obtaining Kerberos ticket for the negotiate queue..."
            "$ROOT/printing/client/kinit_print.sh" ${OCPC_KRB_PRINCIPAL:+"$OCPC_KRB_PRINCIPAL"} \
                || { echo "kinit failed — aborting"; exit 1; }
        fi
        # Sync the print queue's embedded credentials from print_creds.env if
        # present. The SMB password can only live in the CUPS queue (lp has no
        # flag for it), so changing print_creds.env alone isn't enough — this
        # writes it into the queue for you. Set OCPC_SKIP_CREDS=1 to skip.
        if [ -z "${OCPC_SKIP_CREDS:-}" ] && [ -f "$ROOT/printing/client/print_creds.env" ]; then
            echo "syncing print queue credentials from print_creds.env..."
            "$ROOT/printing/client/apply_print_creds.sh" || echo "warning: credential sync failed; continuing"
        fi
        echo "restarting OCPC services..."
        _stop; sleep 1
        _want pinger  && _start pinger  "$PINGER_DIR"  "$PINGER_SCRIPT"  "$PINGER_LOG"  "$PINGER_PID"
        _want printer && _start printer "$PRINTER_DIR" "$PRINTER_SCRIPT" "$PRINTER_LOG" "$PRINTER_PID"
        echo "done. Keep the laptop plugged in with the lid open."
        ;;
esac

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

_stop() {
    for pf in "$PINGER_PID" "$PRINTER_PID"; do
        _alive "$pf" && kill "$(cat "$pf")" 2>/dev/null
        rm -f "$pf"
    done
    # stragglers (e.g. started by hand); daemon argv is the bare script name
    pkill -f 'pinger.py' 2>/dev/null
    pkill -f 'printer.py' 2>/dev/null
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
        echo "restarting OCPC services..."
        _stop; sleep 1
        _start pinger  "$PINGER_DIR"  "$PINGER_SCRIPT"  "$PINGER_LOG"  "$PINGER_PID"
        _start printer "$PRINTER_DIR" "$PRINTER_SCRIPT" "$PRINTER_LOG" "$PRINTER_PID"
        echo "done. Keep the laptop plugged in with the lid open."
        ;;
esac

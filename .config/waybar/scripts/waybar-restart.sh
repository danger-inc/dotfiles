#!/usr/bin/env bash
# Start waybar cleanly (again) – used by Scourge (System → Waybar) and make-cursor.py.
#   waybar-restart.sh            restart immediately (TERM, KILL if needed, then start fresh)
#   waybar-restart.sh --ensure   only start if waybar is not running
#   waybar-restart.sh --soon [s] restart debounced (default 1.2 s; only the last request counts)
# Waybar's output goes to $XDG_RUNTIME_DIR/waybar.log.
RUN="${XDG_RUNTIME_DIR:-/tmp}"
LOG="$RUN/waybar.log"
TICKET="$RUN/waybar-restart.ticket"

start() {
    setsid -f waybar >"$LOG" 2>&1 </dev/null
    for _ in $(seq 30); do pgrep -x waybar >/dev/null && return 0; sleep 0.05; done
    return 1
}

stop() {
    pkill -x waybar || return 0
    for _ in $(seq 20); do pgrep -x waybar >/dev/null || return 0; sleep 0.05; done
    pkill -KILL -x waybar
    for _ in $(seq 20); do pgrep -x waybar >/dev/null || return 0; sleep 0.05; done
}

case "$1" in
    --ensure)
        pgrep -x waybar >/dev/null && exit 0
        start ;;
    --soon)
        delay="${2:-1.2}"
        me="$$-$(date +%s%N)"
        echo "$me" >"$TICKET"
        (
            sleep "$delay"
            [ "$(cat "$TICKET" 2>/dev/null)" = "$me" ] || exit 0
            rm -f "$TICKET"
            stop; start
        ) >/dev/null 2>&1 </dev/null &
        disown ;;
    *)
        stop; start ;;
esac

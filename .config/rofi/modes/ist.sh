#!/usr/bin/env bash
# Fast entry for the own rofi modes: rofi runs ALL modes at start. The launcher
# (launcher.sh) precomputes the lists in parallel into $XDG_RUNTIME_DIR/rofi-ist/<mode>; here the first
# call only reads them (a few milliseconds). Selections and own input go to ist.py.
m=$1; shift
f="${XDG_RUNTIME_DIR:-/tmp}/rofi-ist/$m"
if [ "${ROFI_RETV:-0}" = 0 ]; then
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
        if [ -f "$f" ]; then
            # only fresh lists (from the start that is running right now), otherwise recompute
            if (( EPOCHSECONDS - $(stat -c %Y "$f") < 15 )); then cat "$f"; exit 0; fi
            break
        fi
        [ -d "${f%/*}" ] || break        # started without the launcher: compute it ourselves
        sleep 0.01
    done
fi
exec "${BASH_SOURCE[0]%/*}/ist.py" "$m" "$@"

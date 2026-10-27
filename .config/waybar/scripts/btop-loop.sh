#!/bin/bash
# Runs in the btop window. Super+W now reloads the colors live via SIGUSR2 (apply-colors.sh),
# the restart loop is only a fallback: if the marker is present btop restarts,
# otherwise the window closes normally after q.
mark="${XDG_RUNTIME_DIR:-/tmp}/btop-farben-neu"
while true; do
    btop
    [[ -e $mark ]] || break
    rm -f "$mark"
done

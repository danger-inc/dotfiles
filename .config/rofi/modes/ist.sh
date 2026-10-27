#!/usr/bin/env bash
# Schneller Einstieg für die eigenen rofi-Modi: rofi führt beim Start ALLE Modi aus. Der Starter
# (launcher.sh) berechnet die Listen vorher parallel nach $XDG_RUNTIME_DIR/rofi-ist/<modus>; hier wird beim
# ersten Aufruf nur noch gelesen (wenige Millisekunden). Auswahlen und eigene Eingaben gehen an ist.py.
m=$1; shift
f="${XDG_RUNTIME_DIR:-/tmp}/rofi-ist/$m"
if [ "${ROFI_RETV:-0}" = 0 ]; then
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
        if [ -f "$f" ]; then
            # nur frische Listen (vom gerade laufenden Start), sonst neu berechnen
            if (( EPOCHSECONDS - $(stat -c %Y "$f") < 15 )); then cat "$f"; exit 0; fi
            break
        fi
        [ -d "${f%/*}" ] || break        # ohne Starter gestartet: gleich selbst rechnen
        sleep 0.01
    done
fi
exec "${BASH_SOURCE[0]%/*}/ist.py" "$m" "$@"

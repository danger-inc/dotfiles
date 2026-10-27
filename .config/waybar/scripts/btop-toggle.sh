#!/bin/bash
# Klick auf CPU/RAM: btop gekachelt öffnen, zweiter Klick schließt.
# Kleinere Schrift (9 statt 11), damit btop seine 80×24 Zeichen auch in einer halben oder viertel Kachel bekommt.
if pid=$(hyprctl clients -j | python3 -c 'import json,sys; print(next(str(c["pid"]) for c in json.load(sys.stdin) if c["class"]=="btop"))' 2>/dev/null); then
    kill "$pid"
else
    exec kitty --class btop -o font_size=9 -e ~/.config/waybar/scripts/btop-loop.sh
fi

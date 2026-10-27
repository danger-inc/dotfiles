#!/bin/bash
# Click on CPU/RAM: open btop tiled, a second click closes it.
# Smaller font (9 instead of 11) so btop gets its 80×24 characters even in a half or quarter tile.
if pid=$(hyprctl clients -j | python3 -c 'import json,sys; print(next(str(c["pid"]) for c in json.load(sys.stdin) if c["class"]=="btop"))' 2>/dev/null); then
    kill "$pid"
else
    exec kitty --class btop -o font_size=9 -e ~/.config/waybar/scripts/btop-loop.sh
fi

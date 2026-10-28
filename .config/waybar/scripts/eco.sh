#!/bin/bash
# Energy-saving mode (shared with all apps via ~/.config/ist-eco.json, see istheme.py). Called by the invisible
# waybar module custom/eco every 60 s: switches the mode on automatically at the chosen battery percentage
# (battery menu). Prints nothing visible.
#   eco.sh toggle     switch on/off
IST=~/.local/share/rice-apps/istheme.py
if [[ $1 == toggle ]]; then
    python3 "$IST" eco toggle >/dev/null
    exit 0
fi
python3 "$IST" eco auto >/dev/null
echo '{"text":""}'

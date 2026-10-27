#!/usr/bin/env bash
# Waybar speaker or brightness, left click: show/hide the card (~/.local/share/rice-apps/volume-mixer.py).
#   volume-mixer.sh [audio|bright]   – which content is shown (default: audio)
# The mixer runs permanently in the background (start: "volume-mixer.sh --daemon" from hyprland.lua),
# a click only sends it a signal – so it appears instantly.
# If it is not running (yet), it is started and shown right away.
MIXER='^python3 .*/rice-apps/volume-mixer\.py'
APP="$HOME/.local/share/rice-apps/volume-mixer.py"
export LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so   # gtk4-layer-shell must be loaded before libwayland

if [[ $1 == --daemon ]]; then
    pkill -f "$MIXER"
    exec python3 "$APP"
fi
# bash builtins only, no pkill -f (that alone would need ~100 ms)
# just closed by exactly this click (menu-close-outside.sh was faster)
[[ $1 == bright ]] && mode=bright || mode=audio
read -r prev 2>/dev/null < "$XDG_RUNTIME_DIR/volume-mixer-mode"
if [[ -f $XDG_RUNTIME_DIR/waybar-menu-closed ]]; then
    read -r t n < "$XDG_RUNTIME_DIR/waybar-menu-closed"
    now=${EPOCHREALTIME/[.,]/}
    # only "close" if the same content was open – volume open + click on brightness = switch
    (( ${now:0:13} - t < 400 )) && [[ $n == mixer && $prev == "$mode" ]] && exit 0
fi
echo "$mode" > "$XDG_RUNTIME_DIR/volume-mixer-mode"
read -r pid < "$XDG_RUNTIME_DIR/volume-mixer.pid" 2>/dev/null
kill -USR1 "$pid" 2>/dev/null || setsid -f python3 "$APP" --show >/dev/null 2>&1

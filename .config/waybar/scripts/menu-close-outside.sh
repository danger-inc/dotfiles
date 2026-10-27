#!/usr/bin/env bash
# Called by Hyprland on every left click (see hyprland.lua).
# If the click is outside an open menu (wofi: wifi/bluetooth, rofi: Super+R,
# volume-mixer: volume),
# it is closed. Clicks on windows are caught by click-catcher.py; this script makes sure
# that a click on the waybar closes the menu and still arrives there
# (wofi runs with keyboard "on demand" for that, see menu-lib.sh).

MIXER_OPEN="${XDG_RUNTIME_DIR:-/tmp}/volume-mixer-open"   # exists as long as the mixer is visible
[[ -e $MIXER_OPEN ]] || pgrep -x 'wofi|rofi' >/dev/null || exit 0

source "$HOME/.config/waybar/scripts/menu-lib.sh"

# menu was just opened (e.g. by exactly this click on the icon): leave it alone
if [[ -f $MENU_OPENED ]]; then
    read -r t _ < "$MENU_OPENED"
    (( $(now_ms) - t < 500 )) && exit 0
fi

IFS=', ' read -r cx cy < <(hyprctl cursorpos)
layers=$(hyprctl layers -j)

for name in wofi rofi volume-mixer; do
    read -r x y w h < <(jq -r --arg n "$name" \
        'first(.. | objects | select(.namespace? == $n)) | "\(.x) \(.y) \(.w) \(.h)"' <<<"$layers")
    [[ -n $h ]] || continue
    if (( cx < x || cx >= x + w || cy < y || cy >= y + h )); then
        if [[ $name == volume-mixer ]]; then killed=$(mixer_hide && echo 1); else killed=$(pkill -x "$name" && echo 1); fi
        if [[ -n $killed ]]; then
            read -r _ open < "$MENU_OPENED" 2>/dev/null
            [[ $name == rofi ]] && open=rofi
            [[ $name == volume-mixer ]] && open=mixer
            echo "$(now_ms) $open" > "$MENU_CLOSED"
        fi
    fi
done

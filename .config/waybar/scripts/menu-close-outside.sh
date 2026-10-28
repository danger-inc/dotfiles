#!/usr/bin/env bash
# Called by Hyprland on every left click (see hyprland.lua).
# If the click is outside an open menu (wofi: wifi/bluetooth, rofi: Super+R,
# volume-mixer: volume, swaync: notification panel),
# it is closed. Clicks on windows are caught by click-catcher.py; this script makes sure
# that a click on the waybar closes the menu and still arrives there
# (wofi runs with keyboard "on demand" for that, see menu-lib.sh).

MIXER_OPEN="${XDG_RUNTIME_DIR:-/tmp}/volume-mixer-open"   # exists as long as the mixer is visible
# (the swaync panel is only known to the compositor: one cheap check of the layers)
layers=$(hyprctl layers -j)
[[ -e $MIXER_OPEN ]] || pgrep -x 'wofi|rofi' >/dev/null || grep -q '"swaync-control-center"' <<<"$layers" || exit 0

source "$HOME/.config/waybar/scripts/menu-lib.sh"

# menu was just opened (e.g. by exactly this click on the icon): leave it alone
if [[ -f $MENU_OPENED ]]; then
    read -r t _ < "$MENU_OPENED"
    (( $(now_ms) - t < 500 )) && exit 0
fi

IFS=', ' read -r cx cy < <(hyprctl cursorpos)

for name in wofi rofi volume-mixer swaync-control-center; do
    read -r x y w h < <(jq -r --arg n "$name" \
        'first(.. | objects | select(.namespace? == $n)) | "\(.x) \(.y) \(.w) \(.h)"' <<<"$layers")
    [[ -n $h ]] || continue
    if (( cx < x || cx >= x + w || cy < y || cy >= y + h )); then
        case $name in
            volume-mixer) killed=$(mixer_hide && echo 1) ;;
            swaync-control-center) killed=$(swaync-client -cp -sw >/dev/null && echo 1) ;;
            *) killed=$(pkill -x "$name" && echo 1) ;;
        esac
        if [[ -n $killed ]]; then
            read -r _ open < "$MENU_OPENED" 2>/dev/null
            [[ $name == rofi ]] && open=rofi
            [[ $name == volume-mixer ]] && open=mixer
            [[ $name == swaync-control-center ]] && open=notification
            echo "$(now_ms) $open" > "$MENU_CLOSED"
        fi
    fi
done

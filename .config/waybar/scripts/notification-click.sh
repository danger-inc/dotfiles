#!/usr/bin/env bash
# Click on the bell: notification panel (swaync) on/off – like the menus of the other icons: if another popup is
# open, it is closed by menu-close-outside.sh and the panel opens directly.
source "$HOME/.config/waybar/scripts/menu-lib.sh"
if grep -q '"swaync-control-center"' <<<"$(hyprctl layers -j)"; then
    swaync-client -cp -sw >/dev/null      # open: close (a second click on the same icon)
    echo "$(now_ms) notification" > "$MENU_CLOSED"
    exit 0
fi
if [[ -f $MENU_CLOSED ]]; then            # menu-close-outside.sh was faster and closed it with this very click
    read -r t n < "$MENU_CLOSED"
    (( $(now_ms) - t < 400 )) && [[ $n == notification ]] && exit 0
fi
mixer_hide
pkill -x 'wofi|rofi'
echo "$(now_ms) notification" > "$MENU_OPENED"
swaync-client -op -sw >/dev/null

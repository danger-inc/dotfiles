#!/usr/bin/env bash
# Wird von Hyprland bei jedem Linksklick aufgerufen (siehe hyprland.lua).
# Liegt der Klick außerhalb eines offenen Menüs (wofi: WLAN/Bluetooth, rofi: Super+R,
# volume-mixer: Lautstärke),
# wird es geschlossen. Klicks auf Fenster fängt click-catcher.py ab; dieses Skript sorgt
# dafür, dass ein Klick auf die Waybar das Menü schließt und trotzdem dort ankommt
# (wofi läuft dafür mit Tastatur "bei Bedarf", siehe menu-lib.sh).

MIXER_OPEN="${XDG_RUNTIME_DIR:-/tmp}/volume-mixer-open"   # existiert, solange der Mixer sichtbar ist
[[ -e $MIXER_OPEN ]] || pgrep -x 'wofi|rofi' >/dev/null || exit 0

source "$HOME/.config/waybar/scripts/menu-lib.sh"

# Menü gerade erst geöffnet (z. B. durch genau diesen Klick aufs Icon): in Ruhe lassen
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

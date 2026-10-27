# Gemeinsame Logik für die Waybar-Menüs (wird per "source" eingebunden).

MENU_OPENED="${XDG_RUNTIME_DIR:-/tmp}/waybar-menu-opened"   # "<ms> <menü>"
MENU_CLOSED="${XDG_RUNTIME_DIR:-/tmp}/waybar-menu-closed"   # "<ms> <menü>"
MENU_SCRIPTS="$HOME/.config/waybar/scripts"

now_ms() { date +%s%3N; }

# wofi mit Tastatur "bei Bedarf" statt "exklusiv" (siehe ~/.local/share/rice-apps/wofi-ondemand):
# sonst schickt Hyprland jeden Mausklick an wofi, und ein Klick auf ein anderes Waybar-Icon
# (Bluetooth offen -> WLAN) würde nur das Menü schließen statt direkt umzuschalten.
wofi() { LD_PRELOAD="$HOME/.local/share/rice-apps/wofi-ondemand/wofi-ondemand.so" command wofi "$@"; }

# Lautstärke-Mixer ausblenden, falls sichtbar (Signal an den Hintergrund-Prozess)
mixer_hide() {
    local pid
    [[ -e ${XDG_RUNTIME_DIR:-/tmp}/volume-mixer-open ]] || return 1
    read -r pid < "${XDG_RUNTIME_DIR:-/tmp}/volume-mixer.pid"
    kill -USR2 "$pid" 2>/dev/null
}

# Aufruf: menu_toggle_guard <name>   (z. B. wifi, bluetooth)
# - Klick aufs eigene Icon bei offenem Menü: nur schließen (auch wenn menu-close-outside.sh
#   es durch denselben Klick gerade geschlossen hat).
# - Ein anderes Menü ist offen: das schließen und dieses direkt öffnen.
# Startet außerdem die Klick-Sperre für Fenster (click-catcher.py).
menu_toggle_guard() {
    local name=$1 t n
    mixer_hide
    if pgrep -x wofi >/dev/null; then
        read -r t n < "$MENU_OPENED" 2>/dev/null
        pkill -x wofi
        [[ $n == "$name" ]] && exit 0
    elif [[ -f $MENU_CLOSED ]]; then
        read -r t n < "$MENU_CLOSED"
        (( $(now_ms) - t < 500 )) && [[ $n == "$name" ]] && exit 0
    fi
    echo "$(now_ms) $name" > "$MENU_OPENED"
    menu_catch_clicks
}

# Unsichtbare Fläche über den Fenstern: Klick daneben schließt nur das Menü.
menu_catch_clicks() {
    pkill -f 'python3 .*click-catcher\.py'
    setsid -f "$MENU_SCRIPTS/click-catcher.py" >/dev/null 2>&1
}

# x-Position für ein Menü der Breite $1 (wofi --width): zentriert unter dem Mauszeiger
# (= dem angeklickten Icon), aber nicht über die Ränder der Waybar hinaus.
menu_xoffset() {
    local width=$(( $1 + 14 ))   # wofi rechnet Rahmen/Padding noch dazu
    local bar_margin=50          # margin-left/-right aus config.jsonc
    local cursor_x mon_x mon_w x
    cursor_x=$(hyprctl cursorpos | cut -d, -f1)
    read -r mon_x mon_w < <(hyprctl -j monitors | jq -r '.[] | select(.focused) | "\(.x) \((.width / .scale) | floor)"')
    x=$(( cursor_x - mon_x - width / 2 ))
    (( x > mon_w - bar_margin - width )) && x=$(( mon_w - bar_margin - width ))
    (( x < bar_margin )) && x=$bar_margin
    echo "$x"
}

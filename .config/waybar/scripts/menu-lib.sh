# Shared logic for the waybar menus (included with "source").

MENU_OPENED="${XDG_RUNTIME_DIR:-/tmp}/waybar-menu-opened"   # "<ms> <menu>"
MENU_CLOSED="${XDG_RUNTIME_DIR:-/tmp}/waybar-menu-closed"   # "<ms> <menu>"
MENU_SCRIPTS="$HOME/.config/waybar/scripts"

now_ms() { date +%s%3N; }

# wofi with keyboard "on demand" instead of "exclusive" (see ~/.local/share/rice-apps/wofi-ondemand):
# otherwise Hyprland sends every mouse click to wofi, and a click on another waybar icon
# (bluetooth open -> wifi) would only close the menu instead of switching directly.
wofi() { LD_PRELOAD="$HOME/.local/share/rice-apps/wofi-ondemand/wofi-ondemand.so" command wofi "$@"; }

# hide the volume mixer if visible (signal to the background process)
mixer_hide() {
    local pid
    [[ -e ${XDG_RUNTIME_DIR:-/tmp}/volume-mixer-open ]] || return 1
    read -r pid < "${XDG_RUNTIME_DIR:-/tmp}/volume-mixer.pid"
    kill -USR2 "$pid" 2>/dev/null
}

# Aufruf: menu_toggle_guard <name>   (z. B. wifi, bluetooth)
# - click on its own icon while the menu is open: only close (even if menu-close-outside.sh
#   already closed it with the same click).
# - another menu is open: close it and open this one directly.
# Also starts the click lock for windows (click-catcher.py).
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

# invisible surface above the windows: a click next to the menu only closes the menu.
menu_catch_clicks() {
    pkill -f 'python3 .*click-catcher\.py'
    setsid -f "$MENU_SCRIPTS/click-catcher.py" >/dev/null 2>&1
}

# x position for a menu of width $1 (wofi --width): centered under the mouse pointer
# (= the clicked icon), but not beyond the edges of the waybar.
menu_xoffset() {
    local width=$(( $1 + 14 ))   # wofi adds border/padding on top
    local bar_margin=50          # margin-left/-right from config.jsonc
    local cursor_x mon_x mon_w x
    cursor_x=$(hyprctl cursorpos | cut -d, -f1)
    read -r mon_x mon_w < <(hyprctl -j monitors | jq -r '.[] | select(.focused) | "\(.x) \((.width / .scale) | floor)"')
    x=$(( cursor_x - mon_x - width / 2 ))
    (( x > mon_w - bar_margin - width )) && x=$(( mon_w - bar_margin - width ))
    (( x < bar_margin )) && x=$bar_margin
    echo "$x"
}

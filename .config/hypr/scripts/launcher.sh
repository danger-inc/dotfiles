#!/usr/bin/env bash
# Launcher (Super+R) in the -ist look: rofi with a click lock for windows like the waybar menus.
#   launcher.sh [drun|fenster|filebrowser|rechner|ablage|zeichen|web|system]   (default: drun = apps)
# Pressing the shortcut again closes it.
# Fast: rofi runs all modes at start – the lists of the own modes are precomputed here in parallel
# (~/.config/rofi/modes/ist.sh then only reads them), cleanup runs in the background.
pkill -x rofi && exit 0
source "$HOME/.config/waybar/scripts/menu-lib.sh"
echo "$(now_ms) rofi" > "$MENU_OPENED"
# discard the app cache as soon as programs were (un)installed – otherwise new apps are missing in the launcher
DC="$HOME/.cache/rofi-drun-desktop.cache"
[ -f "$DC" ] && for d in /usr/share/applications "$HOME/.local/share/applications" /var/lib/flatpak/exports/share/applications; do
    [ "$d" -nt "$DC" ] && { rm -f "$DC"; break; }
done
C="${XDG_RUNTIME_DIR:-/tmp}/rofi-ist"
rm -rf "$C"; mkdir -p "$C"
for m in fenster rechner ablage zeichen web system; do
    ( "$HOME/.config/rofi/modes/ist.py" "$m" > "$C/.$m" 2>/dev/null; mv -f "$C/.$m" "$C/$m" ) &
done
( pkill -x wofi; mixer_hide; menu_catch_clicks ) >/dev/null 2>&1 &
exec rofi -show "${1:-drun}"

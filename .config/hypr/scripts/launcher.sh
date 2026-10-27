#!/usr/bin/env bash
# Starter (Super+R) im -ist-Look: rofi mit Klick-Sperre für Fenster wie bei den Waybar-Menüs.
#   launcher.sh [drun|fenster|filebrowser|rechner|ablage|zeichen|web|system]   (Standard: drun = apps)
# Nochmal das Kürzel drücken schließt ihn wieder.
# Schnell: rofi führt beim Start alle Modi aus – die Listen der eigenen Modi werden hier parallel vorberechnet
# (~/.config/rofi/modes/ist.sh liest sie dann nur), Aufräumen läuft im Hintergrund.
pkill -x rofi && exit 0
source "$HOME/.config/waybar/scripts/menu-lib.sh"
echo "$(now_ms) rofi" > "$MENU_OPENED"
# App-Cache verwerfen, sobald Programme (de)installiert wurden – sonst fehlen neue Apps im Starter
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

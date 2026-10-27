#!/usr/bin/env bash
# Waybar-Lautsprecher bzw. -Helligkeit, Linksklick: Karte ein-/ausblenden (~/.local/share/rice-apps/volume-mixer.py).
#   volume-mixer.sh [audio|bright]   – welcher Inhalt gezeigt wird (Standard: audio)
# Der Mixer läuft dauerhaft im Hintergrund (Start: "volume-mixer.sh --daemon" aus hyprland.lua),
# ein Klick schickt ihm nur ein Signal – darum erscheint er sofort.
# Läuft er (noch) nicht, wird er gestartet und gleich angezeigt.
MIXER='^python3 .*/rice-apps/volume-mixer\.py'
APP="$HOME/.local/share/rice-apps/volume-mixer.py"
export LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so   # gtk4-layer-shell muss vor libwayland geladen sein

if [[ $1 == --daemon ]]; then
    pkill -f "$MIXER"
    exec python3 "$APP"
fi
# Nur Bash-Bordmittel, kein pkill -f (das allein bräuchte ~100 ms)
# Gerade eben durch genau diesen Klick geschlossen (menu-close-outside.sh war schneller)
[[ $1 == bright ]] && mode=bright || mode=audio
read -r prev 2>/dev/null < "$XDG_RUNTIME_DIR/volume-mixer-mode"
if [[ -f $XDG_RUNTIME_DIR/waybar-menu-closed ]]; then
    read -r t n < "$XDG_RUNTIME_DIR/waybar-menu-closed"
    now=${EPOCHREALTIME/[.,]/}
    # nur „zu“, wenn derselbe Inhalt offen war – Lautstärke offen + Klick auf Helligkeit = umschalten
    (( ${now:0:13} - t < 400 )) && [[ $n == mixer && $prev == "$mode" ]] && exit 0
fi
echo "$mode" > "$XDG_RUNTIME_DIR/volume-mixer-mode"
read -r pid < "$XDG_RUNTIME_DIR/volume-mixer.pid" 2>/dev/null
kill -USR1 "$pid" 2>/dev/null || setsid -f python3 "$APP" --show >/dev/null 2>&1

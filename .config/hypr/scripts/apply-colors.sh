#!/usr/bin/env bash
# Erzeugt aus einem Bild die Systemfarben (matugen) und lädt alle Programme neu.
# Aufruf: apply-colors.sh /pfad/zum/bild
# Vorlagen und Zuordnung: ~/.config/matugen/config.toml

img=$1
[[ -f $img ]] || { echo "Image not found: $img" >&2; exit 1; }

matugen image "$img" -m dark --source-color-index 0 -q || exit 1
~/.local/share/rice-apps/cursor/make-cursor.py --apply >/dev/null &   # Cursor zuerst, parallel zum Rest

# Leiste + Terminal: Farben der Suite-Auswahl (hell/dunkel) nach ~/.cache/ist, lädt Waybar (CSS) und Kitty neu
~/.local/share/rice-apps/ist-colors.py --no-reload
swaync-client -rs >/dev/null 2>&1         # Benachrichtigungen
hyprctl reload >/dev/null                 # Fensterrahmen
pkill -USR2 -x btop                       # btop: Farben live neu laden (kein Neustart, Graphen bleiben)
# wofi, rofi, wlogout und hyprlock lesen die Farben beim nächsten Öffnen

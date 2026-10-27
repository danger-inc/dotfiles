#!/usr/bin/env bash
# Creates the system colors (matugen) from an image and reloads all programs.
# Aufruf: apply-colors.sh /pfad/zum/bild
# Templates and mapping: ~/.config/matugen/config.toml

img=$1
[[ -f $img ]] || { echo "Image not found: $img" >&2; exit 1; }

matugen image "$img" -m dark --source-color-index 0 -q || exit 1
~/.local/share/rice-apps/cursor/make-cursor.py --apply >/dev/null &   # cursor first, in parallel with the rest

# bar + terminal: colors of the suite choice (light/dark) to ~/.cache/ist, reloads waybar (CSS) and kitty
~/.local/share/rice-apps/ist-colors.py --no-reload
swaync-client -rs >/dev/null 2>&1         # Benachrichtigungen
hyprctl reload >/dev/null                 # Fensterrahmen
pkill -USR2 -x btop                       # btop: reload colors live (no restart, graphs stay)
# wofi, rofi, wlogout and hyprlock read the colors on next open

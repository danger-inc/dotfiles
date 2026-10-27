#!/bin/bash
# Super+W: zufälliges Hintergrundbild (nie das aktuelle) + passende Systemfarben
# Eigene Bilder: ~/.config/wallpapers (wallist verwaltet den Ordner). Ist er leer, wird das mitgelieferte Bild kopiert.

dir=~/.config/wallpapers
mkdir -p "$dir"
if [ -z "$(find "$dir" -type f -print -quit)" ]; then
    cp ~/.config/hypr/default-wallpaper.jpg "$dir/default.jpg" || exit 1
fi

current=$(cat ~/.cache/matugen/wallpaper 2>/dev/null)
wall=$(find "$dir" -type f ! -path "$current" | shuf -n 1)
[ -n "$wall" ] || wall=$(find "$dir" -type f | shuf -n 1)   # nur ein Bild vorhanden
[ -n "$wall" ] || exit 1

awww img "$wall"
~/.config/hypr/scripts/apply-colors.sh "$wall"

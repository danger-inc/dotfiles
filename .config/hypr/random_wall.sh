#!/bin/bash
# Super+W: random wallpaper (never the current one) + matching system colors
# Own images: ~/.config/wallpapers (wallist manages the folder). If it is empty, the bundled image is copied.

dir=~/.config/wallpapers
mkdir -p "$dir"
if [ -z "$(find "$dir" -type f -print -quit)" ]; then
    cp ~/.config/hypr/default-wallpaper.jpg "$dir/default.jpg" || exit 1
fi

current=$(cat ~/.cache/matugen/wallpaper 2>/dev/null)
wall=$(find "$dir" -type f ! -path "$current" | shuf -n 1)
[ -n "$wall" ] || wall=$(find "$dir" -type f | shuf -n 1)   # only one image available
[ -n "$wall" ] || exit 1

awww img "$wall"
~/.config/hypr/scripts/apply-colors.sh "$wall"

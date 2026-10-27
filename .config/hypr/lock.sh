#!/bin/bash
# Lock screen: provide the current wallpaper for hyprlock and lock (Super+L, launcher, hypridle).
pidof hyprlock >/dev/null && exit 0
mkdir -p ~/.cache
img=$(awww query 2>/dev/null | sed -n 's/.*image: //p' | head -1)
if [[ -f "$img" ]]; then cp "$img" ~/.cache/current_wallpaper.png
elif [[ -s ~/.cache/matugen/wallpaper && -f "$(cat ~/.cache/matugen/wallpaper)" ]]; then cp "$(cat ~/.cache/matugen/wallpaper)" ~/.cache/current_wallpaper.png
elif [[ ! -f ~/.cache/current_wallpaper.png ]]; then cp ~/.config/hypr/default-wallpaper.jpg ~/.cache/current_wallpaper.png; fi
exec hyprlock

#!/usr/bin/env bash
# Small menu for the datist module in waybar (left click on the next appointment; right click opens datist):
# hide this appointment / its whole series / all appointments in the bar, show them again, open datist.

source "$HOME/.config/waybar/scripts/menu-lib.sh"
menu_toggle_guard datist

DATIST="$HOME/.local/bin/datist"
info=$("$DATIST" --bar-info 2>/dev/null) || exit 0
on=$(jq -r '.on' <<<"$info")
hidden=$(jq -r '.hidden' <<<"$info")
title=$(jq -r '.title' <<<"$info")
recurring=$(jq -r '.recurring' <<<"$info")
(( ${#title} > 18 )) && title="${title:0:17}…"

entries=()
declare -A actions

label="󰃭  datist öffnen"
entries+=("$label"); actions[$label]="$DATIST"

if [[ $on == "true" && -n $title ]]; then
    if [[ $recurring == "true" ]]; then
        label="󰈉  diese verstecken"
        entries+=("$label"); actions[$label]="$DATIST --bar-hide once"
        label="󰈉  ganze serie verstecken"
        entries+=("$label"); actions[$label]="$DATIST --bar-hide series"
    else
        label="󰈉  termin verstecken"
        entries+=("$label"); actions[$label]="$DATIST --bar-hide once"
    fi
fi
if [[ $on == "true" ]]; then
    label="󰛑  alle verstecken"
    entries+=("$label"); actions[$label]="$DATIST --bar-off"
fi
if [[ $on != "true" || $hidden -gt 0 ]]; then
    label="󰈈  alle zeigen"
    [[ $hidden -gt 0 ]] && label+="  · $hidden"
    entries+=("$label"); actions[$label]="$DATIST --bar-show-all"
fi
label="󰒓  einstellungen"
entries+=("$label"); actions[$label]="$DATIST --tab bar"

choice=$(printf '%s\n' "${entries[@]}" | wofi --dmenu \
    --style "$HOME/.config/wofi/style.css" \
    --prompt "${title:-datist}" \
    --width 290 --lines ${#entries[@]} \
    --location top_left --xoffset "$(menu_xoffset 290)" --yoffset 10)

[[ -n $choice && -n ${actions[$choice]} ]] || exit 0
setsid -f bash -c "${actions[$choice]}" >/dev/null 2>&1

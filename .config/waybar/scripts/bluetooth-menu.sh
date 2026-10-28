#!/usr/bin/env bash
# Small bluetooth menu for waybar (left click on the bluetooth module).
# Replaces the context menu of the blueman tray icon.

source "$HOME/.config/waybar/scripts/menu-lib.sh"
menu_toggle_guard bluetooth

powered=$(bluetoothctl show | awk '/Powered:/ {print $2}')

entries=()
declare -A actions

if [[ $powered == "yes" ]]; then
    label="󰂲  turn bluetooth off"
    entries+=("$label")
    actions[$label]="bluetoothctl power off"

    while read -r _ mac name; do
        [[ -z $mac ]] && continue
        if bluetoothctl info "$mac" | grep -q "Connected: yes"; then
            label="󰂱  $name  · connected – disconnect"
            actions[$label]="bluetoothctl disconnect $mac"
        else
            label="󰂯  $name  · connect"
            actions[$label]="bluetoothctl connect $mac"
        fi
        entries+=("$label")
    done < <(bluetoothctl devices Paired)
else
    label="󰂯  turn bluetooth on"
    entries+=("$label")
    actions[$label]="rfkill unblock bluetooth && sleep 1 && bluetoothctl power on"
fi

label="󰒓  manage devices …"
entries+=("$label")
actions[$label]="$HOME/.local/bin/rice-bluetooth"

choice=$(printf '%s\n' "${entries[@]}" | wofi --dmenu \
    --style "$HOME/.config/wofi/style.css" \
    --prompt "bluetooth" \
    --width 380 --lines ${#entries[@]} \
    --location top_left --xoffset "$(menu_xoffset 380)" --yoffset 10)

[[ -n $choice && -n ${actions[$choice]} ]] || exit 0
setsid -f bash -c "${actions[$choice]}" >/dev/null 2>&1

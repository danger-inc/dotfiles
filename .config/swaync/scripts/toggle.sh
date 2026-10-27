#!/usr/bin/env bash
# Quick toggles in the notification panel (swaync buttons-grid).
#   toggle.sh <wifi|bluetooth|mute>          switches to $SWAYNC_TOGGLE_STATE (true/false)
#   toggle.sh <wifi|bluetooth|mute> state    prints true/false (shown when opening)
#   toggle.sh lock | power                   close the panel, open lock / power menu
what=$1 mode=$2
on=false; [[ $SWAYNC_TOGGLE_STATE == true ]] && on=true

case $what in
    wifi)
        if [[ $mode == state ]]; then [[ $(nmcli radio wifi) == enabled ]] && echo true || echo false
        elif $on; then nmcli radio wifi on; else nmcli radio wifi off; fi ;;
    bluetooth)
        if [[ $mode == state ]]; then bluetoothctl show | grep -q "Powered: yes" && echo true || echo false
        elif $on; then rfkill unblock bluetooth; sleep 1; bluetoothctl power on; else bluetoothctl power off; fi ;;
    mute)
        if [[ $mode == state ]]; then wpctl get-volume @DEFAULT_AUDIO_SINK@ | grep -q MUTED && echo true || echo false
        elif $on; then wpctl set-mute @DEFAULT_AUDIO_SINK@ 1; else wpctl set-mute @DEFAULT_AUDIO_SINK@ 0; fi ;;
    lock)  swaync-client -cp; hyprlock ;;
    power) swaync-client -cp; ~/.config/wlogout/launch.sh ;;
esac

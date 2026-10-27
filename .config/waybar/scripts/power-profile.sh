#!/bin/bash
# Right click on the battery: switch between the power profiles and briefly show which one is active now.
mapfile -t profiles < <(powerprofilesctl list | sed -n 's/^[ *]*\([a-z-]*\):$/\1/p')
cur=$(powerprofilesctl get)
for i in "${!profiles[@]}"; do [[ ${profiles[$i]} == "$cur" ]] && next=${profiles[$(( (i + 1) % ${#profiles[@]} ))]}; done
powerprofilesctl set "$next"
declare -A name=([power-saver]="Stromsparen" [balanced]="Ausgewogen" [performance]="Leistung")
notify-send -a "Akku" -t 2000 "Energieprofil: ${name[$next]:-$next}"

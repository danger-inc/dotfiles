#!/bin/bash
# Rechtsklick auf den Akku: zwischen den Energieprofilen wechseln und kurz anzeigen, welches jetzt aktiv ist.
mapfile -t profiles < <(powerprofilesctl list | sed -n 's/^[ *]*\([a-z-]*\):$/\1/p')
cur=$(powerprofilesctl get)
for i in "${!profiles[@]}"; do [[ ${profiles[$i]} == "$cur" ]] && next=${profiles[$(( (i + 1) % ${#profiles[@]} ))]}; done
powerprofilesctl set "$next"
declare -A name=([power-saver]="Stromsparen" [balanced]="Ausgewogen" [performance]="Leistung")
notify-send -a "Akku" -t 2000 "Energieprofil: ${name[$next]:-$next}"

#!/usr/bin/env bash
# Super+Scroll: nächster/vorheriger Desktop MIT Fenstern in Scrollrichtung; gibt es keinen, dann der
# unmittelbar benachbarte (1..10) – so kommt man von 2 (allein) sowohl nach 1 als auch nach 3,
# und mit Fenstern auf 1 und 3 wird die leere 2 übersprungen.
# ws-scroll.sh up|down   (down = höhere Nummer)
dir=$1
cur=$(hyprctl activeworkspace -j | jq '.id')
occ=$(hyprctl workspaces -j | jq -c '[.[] | select(.windows>0 and .id>0) | .id]')
t=$(jq -n --argjson o "$occ" --argjson c "$cur" --arg d "$dir" '
  if $d=="down" then ([$o[]|select(.>$c)]|min) // ([$c+1,10]|min)
  else ([$o[]|select(.<$c)]|max) // ([$c-1,1]|max) end')
[ "$t" != "$cur" ] && hyprctl dispatch workspace "$t" >/dev/null

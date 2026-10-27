#!/usr/bin/env bash
# Super+Scroll: next/previous desktop WITH windows in the scroll direction; if there is none, the
# directly adjacent one (1..10) – so from 2 (alone) you reach both 1 and 3,
# and with windows on 1 and 3 the empty 2 is skipped.
# ws-scroll.sh up|down   (down = higher number)
dir=$1
cur=$(hyprctl activeworkspace -j | jq '.id')
occ=$(hyprctl workspaces -j | jq -c '[.[] | select(.windows>0 and .id>0) | .id]')
t=$(jq -n --argjson o "$occ" --argjson c "$cur" --arg d "$dir" '
  if $d=="down" then ([$o[]|select(.>$c)]|min) // ([$c+1,10]|min)
  else ([$o[]|select(.<$c)]|max) // ([$c-1,1]|max) end')
[ "$t" != "$cur" ] && hyprctl dispatch workspace "$t" >/dev/null

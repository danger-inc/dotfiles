#!/usr/bin/env bash
# Small menu for the battery module in waybar (left click; right click: remaining time/percent via format-alt):
# energy-saving mode on/off and its settings (shared by all apps, see ~/.local/share/rice-apps/istheme.py).

source "$HOME/.config/waybar/scripts/menu-lib.sh"
menu_toggle_guard battery

IST="$HOME/.local/share/rice-apps/istheme.py"
cfg=$(python3 "$IST" eco json) || exit 0
j() { jq -r ".$1" <<<"$cfg"; }
box() { [[ $1 == true ]] && echo "[■]" || echo "[ ]"; }

bat=/sys/class/power_supply/BAT0
pct=$(<"$bat/capacity"); status=$(<"$bat/status")
case $status in
    Charging) st="lädt" ;; Full) st="voll" ;; Discharging) st="entlädt" ;; *) st="netzteil" ;;
esac
# remaining time from the energy flow (like waybar)
t=""
read -r now < "$bat/charge_now" 2>/dev/null; read -r full < "$bat/charge_full" 2>/dev/null; read -r pw < "$bat/current_now" 2>/dev/null
if [[ ${pw:-0} -gt 0 ]]; then
    if [[ $status == Discharging ]]; then m=$(( now * 60 / pw )); elif [[ $status == Charging ]]; then m=$(( (full - now) * 60 / pw )); fi
    [[ -n $m ]] && t=$(printf '  · %d:%02d h' $((m / 60)) $((m % 60)))
fi

entries=()
declare -A actions
add() { entries+=("$1"); actions[$1]="$2"; }

entries+=("󰁹  $pct %  ·  $st$t")      # information only
add "$(box "$(j on)")  energiesparmodus" "toggle"
add "$(box "$(j hypr)")  desktop-animationen & blur aus" "opt hypr $([[ $(j hypr) == true ]] && echo false || echo true)"
at=$(j auto_at)
case $at in
    0)  add "[ ]  automatisch einschalten: aus" "opt auto_at 20" ;;
    20) add "[■]  automatisch bei ≤ 20 % akku" "opt auto_at 30" ;;
    *)  add "[■]  automatisch bei ≤ 30 % akku" "opt auto_at 0" ;;
esac

choice=$(printf '%s\n' "${entries[@]}" | wofi --dmenu \
    --style "$HOME/.config/wofi/style.css" \
    --prompt "akku" \
    --width 330 --lines ${#entries[@]} \
    --location top_left --xoffset "$(menu_xoffset 330)" --yoffset 10)

[[ -n $choice && -n ${actions[$choice]} ]] || exit 0
case ${actions[$choice]} in
    toggle) python3 "$IST" eco toggle >/dev/null ;;
    opt*)   read -r _ k v <<<"${actions[$choice]}"; python3 "$IST" eco option "$k" "$v" >/dev/null ;;
esac
